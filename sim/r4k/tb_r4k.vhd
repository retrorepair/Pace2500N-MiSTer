-- Bench for the vendored CPU (rtl/r4k) running the real U202 from reset, big-endian.
-- Memory model on clk1x with the KI bridge's handshake (grant on a read's start; line
-- reads = four 64-bit beats from the 32-byte line start with ddr3_DOUT_READY, mem_done
-- beside the last; uncached reads return the 32-bit word in bits 31:0 by address bit 2).
-- DDR words hold bytes in address order, lane 0 = lowest address (as the MiSTer core's
-- DDR3 images). Physical map as the Pace: RAM 0x00000000-0x00FFFFFF, flash
-- 0x1FC00000-0x1FDFFFFF, device registers 0x10000000-0x1FBFFFFF read 0 (as the reference
-- bench's mmio_policy 1) and writes are logged.
-- Trace: one line per retired instruction "index pc mode reg value" (as tb_ref_trace.sv).
-- Generics: N = instructions to run, FLASH_HEX, TRACE.
library IEEE;
use IEEE.std_logic_1164.all;
use IEEE.numeric_std.all;
use std.textio.all;
use work.pexport.all;

entity tb_r4k is
   generic
   (
      N         : integer := 100000;
      FLASH_HEX : string  := "sim/fullflash_ddr.hex";
      TRACE     : string  := "sim/r4k/r4k_trace.txt";
      WATCH     : integer := 0;  -- physical RAM address: report every write to its 64-bit word
      -- Start from a dump of the reference CPU (sim/r4k/tb_ref_trace.sv +dump=K) instead of reset:
      START_STATE : string := "";   -- 68 hex words: GPR, CP0, PC, MIPS16, HI, LO
      START_RAM   : string := "";   -- DDR words, $writememh layout
      LAT         : integer := 0;   -- clk1x cycles before a read's grant / a write's done (bus latency)
      GAP         : integer := 6;   -- clk1x cycles from grant to the first data (rtl/pace_r4k.sv: 1)
      LAT_RAND    : integer := 0    -- if > 0: each access adds 0..LAT_RAND-1 cycles (LFSR), as DDR contention does
   );
end entity;

architecture sim of tb_r4k is
   signal clk1x, clk2x : std_logic := '0';
   signal reset        : std_logic := '1';

   signal mem_request, mem_rnw, mem_req64, mem_line_write, mem_line_ra : std_logic;
   signal mem_address  : unsigned(31 downto 0);
   signal mem_size     : unsigned(2 downto 0);
   signal mem_writeMask : std_logic_vector(7 downto 0);
   signal mem_dataWrite : std_logic_vector(63 downto 0);
   signal mem_line_data : std_logic_vector(255 downto 0);
   signal mem_line_bytes : std_logic_vector(31 downto 0);
   signal mem_dataRead : std_logic_vector(63 downto 0) := (others => '0');
   signal mem_done, grant, dout_ready : std_logic := '0';
   signal dout         : std_logic_vector(63 downto 0) := (others => '0');
   signal cpu_done     : std_logic;
   signal cpu_export   : cpu_export_type;
   signal errors       : std_logic_vector(5 downto 0);
   signal ckpt_valid, ckpt_wr : std_logic := '0';
   signal ckpt_index   : unsigned(6 downto 0) := (others => '0');
   signal ckpt_data    : std_logic_vector(31 downto 0) := (others => '0');

   -- 32-bit words, index = physical address / 4, value as stored in DDR (lane order).
   type t_mem is array(natural range <>) of std_logic_vector(31 downto 0);
   subtype t_w64 is std_logic_vector(63 downto 0);
begin
   clk2x <= not clk2x after 5 ns;
   clk1x <= not clk1x after 10 ns;

   core : entity work.cpu
   generic map (LITTLE_ENDIAN => false, NO_ADDRESS_ERROR => true, COUNT_NUM => 81, COUNT_DEN => 400)
   port map
   (
      clk1x => clk1x, clk2x => clk2x, reset_1x => reset, reset_2x => reset,
      DATACACHEWRITETHROUGH => '0', irqRequest => "00", cpuPaused => '0',
      error_instr => errors(0), error_stall => errors(1), error_FPU => errors(2),
      error_exception => errors(3), error_fifo => errors(4), error_TLB => errors(5),
      debug_fetch_pc => open, debug_retired => open, debug_retire_pc => open, debug_retire_opcode => open,
      debug_cop0_cause_live => open, debug_cop0_epc_live => open, debug_perf_events => open,
      cpu_done => cpu_done, cpu_export => cpu_export,
      mem_request => mem_request, mem_rnw => mem_rnw, mem_address => mem_address,
      mem_req64 => mem_req64, mem_size => mem_size, mem_writeMask => mem_writeMask,
      mem_dataWrite => mem_dataWrite, mem_line_write => mem_line_write, mem_line_ra => mem_line_ra,
      mem_line_data => mem_line_data, mem_line_bytes => mem_line_bytes,
      mem_dataRead => mem_dataRead, mem_done => mem_done, rdram_granted2x => grant,
      ddr3_DOUT => dout, ddr3_DOUT_READY => dout_ready,
      fast_ok => '0', fast_req_tog => open, fast_req_line => open, fast_req_stream => open,
      ckpt_valid => ckpt_valid, ckpt_wr => ckpt_wr, ckpt_index => ckpt_index, ckpt_data => ckpt_data
   );

   -- Memory: one transaction at a time, fixed latency.
   memory : process
      variable ram   : t_mem(0 to 4194303);  -- 16 MiB
      variable flash : t_mem(0 to 524287);   -- 2 MiB
      file f : text;
      variable l : line;
      variable w64 : std_logic_vector(63 downto 0);
      variable k : integer := 0;
      variable a : unsigned(31 downto 0);
      variable phys : unsigned(28 downto 0);
      variable rnw, req64, lw : std_logic;
      variable size : unsigned(2 downto 0);
      variable mask : std_logic_vector(7 downto 0);
      variable wdata : std_logic_vector(63 downto 0);
      variable ldata : std_logic_vector(255 downto 0);
      variable lbytes : std_logic_vector(31 downto 0);
      variable ckpt_w : std_logic_vector(31 downto 0);
      variable tl : line;
      variable lfsr  : unsigned(31 downto 0) := x"1D872B41";
      variable extra : integer := 0;
      file mmio_log : text open write_mode is "sim/r4k/r4k_mmio.txt";

      impure function rd64(p : unsigned(28 downto 0)) return t_w64 is
         variable i : integer;
      begin
         if p < x"1000000" then
            i := to_integer(p(23 downto 3)) * 2;
            return ram(i + 1) & ram(i);
         elsif p >= x"1FC00000" and p < x"1FE00000" then
            i := to_integer(p(20 downto 3)) * 2;
            return flash(i + 1) & flash(i);
         elsif p(28 downto 3) = to_unsigned(16#2001224#, 26) then
            -- As the reference bench (pace_firmware_cpu EXPERIMENTAL_READY, mmio_policy 1):
            -- B0009120 reads 0x00000020, every other device register 0. Test stand-in only.
            return x"00000000" & x"20000000";
         else
            return (others => '0');
         end if;
      end function;

      procedure wr64(p : unsigned(28 downto 0); d : std_logic_vector(63 downto 0); m : std_logic_vector(7 downto 0)) is
         variable i : integer;
         variable w : std_logic_vector(31 downto 0);
      begin
         if p < x"1000000" then
            i := to_integer(p(23 downto 3)) * 2;
            if WATCH /= 0 and to_integer(p(23 downto 3)) = WATCH / 8 then
               report "WATCH write " & to_hstring(p) & " mask " & to_hstring(m) & " data " & to_hstring(d);
            end if;
            for h in 0 to 1 loop
               w := ram(i + h);
               for b in 0 to 3 loop
                  if m(h * 4 + b) = '1' then w(b * 8 + 7 downto b * 8) := d(h * 32 + b * 8 + 7 downto h * 32 + b * 8); end if;
               end loop;
               ram(i + h) := w;
            end loop;
         elsif p >= x"10000000" and p < x"1FC00000" then
            write(tl, string'("M W ")); hwrite(tl, std_logic_vector(p)); write(tl, string'(" "));
            write(tl, m); write(tl, string'(" ")); hwrite(tl, d); writeline(mmio_log, tl);
         else
            report "write outside RAM/devices: " & to_hstring(p) severity failure;
         end if;
      end procedure;
   begin
      for i in ram'range loop ram(i) := (others => '0'); end loop;
      file_open(f, FLASH_HEX, read_mode);
      while not endfile(f) and k < 262144 loop
         readline(f, l);
         if l'length >= 16 then
            hread(l, w64);
            flash(k * 2) := w64(31 downto 0); flash(k * 2 + 1) := w64(63 downto 32);
            k := k + 1;
         end if;
      end loop;
      file_close(f);
      report "flash loaded: " & integer'image(k) & " DDR words";
      if START_RAM /= "" then
         file_open(f, START_RAM, read_mode); k := 0;
         while not endfile(f) and k < 2097152 loop
            readline(f, l);
            if l'length >= 16 and l(l'low) /= '/' then
               hread(l, w64);
               ram(k * 2) := w64(31 downto 0); ram(k * 2 + 1) := w64(63 downto 32);
               k := k + 1;
            end if;
         end loop;
         file_close(f);
         report "RAM loaded: " & integer'image(k) & " DDR words";
      end if;
      if START_STATE /= "" then
         file_open(f, START_STATE, read_mode);
         for i in 0 to 67 loop
            readline(f, l); hread(l, ckpt_w);
            wait until rising_edge(clk2x);
            ckpt_wr <= '1'; ckpt_index <= to_unsigned(i, 7); ckpt_data <= ckpt_w;
         end loop;
         wait until rising_edge(clk2x);
         ckpt_wr <= '0'; ckpt_valid <= '1';
         file_close(f);
         report "state loaded";
      end if;
      wait for 100 ns;
      wait until rising_edge(clk1x);
      reset <= '0';
      loop
         wait until rising_edge(clk1x);
         mem_done <= '0'; grant <= '0'; dout_ready <= '0';
         if mem_request = '1' then
            a := mem_address; phys := a(28 downto 0); rnw := mem_rnw; req64 := mem_req64;
            size := mem_size; mask := mem_writeMask; wdata := mem_dataWrite;
            lw := mem_line_write; ldata := mem_line_data; lbytes := mem_line_bytes;
            if WATCH /= 0 and to_integer(phys(23 downto 5)) = WATCH / 32 and phys < x"1000000" then
               report "WATCH request " & to_hstring(a) & " rnw " & std_logic'image(rnw) & " size " & to_hstring(size) &
                      " line_write " & std_logic'image(lw) & " ra " & std_logic'image(mem_line_ra) & " mask " & to_hstring(mask);
            end if;
            lfsr := lfsr(30 downto 0) & (lfsr(31) xor lfsr(21) xor lfsr(1) xor lfsr(0));
            if LAT_RAND > 0 then extra := to_integer(lfsr(15 downto 0)) mod LAT_RAND; else extra := 0; end if;
            if rnw = '1' then
               for d in 0 to LAT + extra loop wait until rising_edge(clk1x); end loop;
               grant <= '1';
               for d in 1 to GAP loop wait until rising_edge(clk1x); grant <= '0'; end loop;
               if size = "100" then
                  for beat in 0 to 3 loop
                     dout <= rd64((phys(28 downto 5) & "00000") + to_unsigned(beat * 8, 29));
                     dout_ready <= '1';
                     if beat = 3 then mem_done <= '1'; end if;
                     wait until rising_edge(clk1x);
                     dout_ready <= '0'; mem_done <= '0';
                  end loop;
               else
                  w64 := rd64(phys(28 downto 3) & "000");
                  if phys >= x"10000000" and phys < x"1FC00000" then
                     write(tl, string'("M R ")); hwrite(tl, std_logic_vector(phys)); writeline(mmio_log, tl);
                  end if;
                  if req64 = '1' then mem_dataRead <= w64;
                  elsif phys(2) = '1' then mem_dataRead <= x"00000000" & w64(63 downto 32);
                  else mem_dataRead <= x"00000000" & w64(31 downto 0); end if;
                  mem_done <= '1';
                  wait until rising_edge(clk1x);
                  mem_done <= '0';
               end if;
            else
               for d in 1 to 3 + LAT + extra loop wait until rising_edge(clk1x); end loop;
               if lw = '1' then
                  for q in 0 to 3 loop
                     if mask(q) = '1' then
                        wr64((phys(28 downto 5) & "00000") + to_unsigned(q * 8, 29),
                             ldata(q * 64 + 63 downto q * 64), lbytes(q * 8 + 7 downto q * 8));
                     end if;
                  end loop;
               elsif req64 = '0' and phys(2) = '1' then
                  -- A 32-bit write carries its word in bits 31:0 with mask bits 3:0;
                  -- address bit 2 picks the half of the DDR word (as reads).
                  wr64(phys(28 downto 3) & "000", wdata(31 downto 0) & x"00000000", mask(3 downto 0) & "0000");
               else
                  wr64(phys(28 downto 3) & "000", wdata, mask);
               end if;
               mem_done <= '1';
               wait until rising_edge(clk1x);
               mem_done <= '0';
            end if;
         end if;
      end loop;
   end process;

   -- Architectural trace at retirement.
   tracer : process
      file t : text open write_mode is TRACE;
      variable l : line;
      variable prev : tExportRegs := (others => (others => '0'));
      variable idx  : integer := 0;
      variable r    : integer;
   begin
      wait until reset = '0';
      loop
         wait until rising_edge(clk2x);
         if cpu_done = '1' then
            r := 0;
            for i in 1 to 31 loop
               if cpu_export.regs(i) /= prev(i) then r := i; end if;
            end loop;
            write(l, integer'image(idx)); write(l, string'(" "));
            hwrite(l, std_logic_vector(cpu_export.pc(31 downto 0))); write(l, string'(" 0 "));
            write(l, integer'image(r)); write(l, string'(" "));
            if r /= 0 then hwrite(l, std_logic_vector(cpu_export.regs(r)(31 downto 0)));
            else write(l, string'("00000000")); end if;
            writeline(t, l);
            prev := cpu_export.regs;
            idx := idx + 1;
            if idx >= N then
               report "done: " & integer'image(idx) & " instructions" severity note;
               std.env.finish;
            end if;
         end if;
         if errors /= "000000" then
            report "CPU error flags " & to_hstring(errors) & " after " & integer'image(idx) & " instructions" severity failure;
         end if;
      end loop;
   end process;
end architecture;
