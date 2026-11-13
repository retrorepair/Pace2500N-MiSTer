library IEEE;
use IEEE.std_logic_1164.all;
use IEEE.numeric_std.all;

library mem;
use work.pFunctions.all;

-- NEC VR4110 primary data cache for the Pace 2500N: 8 KiB, direct mapped, 16-byte lines,
-- write back (the firmware sizes and sweeps it so: boot BFC00910.., flush 80007EAC..).
--
-- The logic is the N64 core's VR4300 data cache (github.com/MiSTer-devel/N64_MiSTer,
-- rtl/cpu_datacache.vhd, Robert Peip, GPL-3.0), which has exactly this shape, placed behind
-- the port of the KI CPU's data cache (cpu_datacache_ki.vhd) that cpu.vhd drives:
--  - one CPU clock (clk2x, the N64's clk93); fills land on clk1x as the KI bridge delivers them;
--  - the KI memory path moves 32-byte lines: a fill returns the four qwords of the 32-byte
--    region and this cache keeps the two of its 16-byte line; a write-back sends four beats of
--    that region with writeback_mask/bytes naming only this line's two qwords;
--  - bus data in address order (lane 0 = lowest address), as cpu.vhd's bus_to_cpu*/cpu_to_bus*
--    and the uncached path use: fills are stored as they come, write-backs leave as stored
--    (no half swap - the N64's DDR3 RDRAM layout is not this bus);
--  - KI-only features have no counterpart here and their outputs are idle: read-ahead,
--    framebuffer partial stores, the store buffer, early restart, way prediction.
entity cpu_datacache is
   generic
   (
      LITTLE_ENDIAN : boolean := false
   );
   port
   (
      clk1x             : in  std_logic;
      clk2x             : in  std_logic;
      reset_1x          : in  std_logic;
      reset_2x          : in  std_logic;
      stall             : in  unsigned(4 downto 0);
      stall4            : in  std_logic;
      fifo_block        : in  std_logic;

      write_through_in  : in  std_logic := '0';

      ram_request       : out std_logic := '0';
      ram_reqAddr       : out unsigned(31 downto 0) := (others => '0');
      ram_active        : in  std_logic := '0';
      ram_grant         : in  std_logic := '0';
      ram_done          : in  std_logic := '0';
      fill_last_q       : out std_logic;
      wb_hold           : out std_logic := '0';
      ddr3_DOUT         : in  std_logic_vector(63 downto 0);
      ddr3_DOUT_READY   : in  std_logic;

      writeback_ena     : out std_logic := '0';
      writeback_addr    : out unsigned(31 downto 0) := (others => '0');
      writeback_data    : out std_logic_vector(63 downto 0) := (others => '0');
      writeback_mask    : out std_logic_vector(3 downto 0) := (others => '1');
      writeback_bytes   : out std_logic_vector(31 downto 0) := (others => '1');

      tag_addr          : in  unsigned(31 downto 0);
      next_load         : in  std_logic := '1';

      read_ena          : in  std_logic;
      RW_addr           : in  unsigned(31 downto 0);
      RW_64             : in  std_logic;
      RW_fb             : in  std_logic := '0';
      read_busy         : out std_logic;
      read_done         : out std_logic;
      read_data         : out std_logic_vector(63 downto 0) := (others => '0');

      write_ena         : in  std_logic;
      write_be          : in  std_logic_vector(7 downto 0);
      write_data        : in  std_logic_vector(63 downto 0);
      write_done        : out  std_logic;

      CacheCommandEna   : in  std_logic;
      CacheCommand      : in  unsigned(4 downto 0);
      CachecommandStall : out std_logic;
      CachecommandDone  : out std_logic := '0';

      TagLo_Valid       : in  std_logic;
      TagLo_Dirty       : in  std_logic;
      TagLo_Addr        : in  unsigned(19 downto 0);

      writeTagEna       : out std_logic := '0';
      writeTagValue     : out unsigned(21 downto 0) := (others => '0');

      clear_busy        : out std_logic;
      debug_state       : out std_logic_vector(4 downto 0) := (others => '0');
      perf_miss         : out std_logic := '0';
      perf_miss_low     : out std_logic := '0';
      perf_stride_hit   : out std_logic := '0';
      perf_delta_hit    : out std_logic := '0';
      perf_fill_wait    : out std_logic := '0';
      perf_fill_data    : out std_logic := '0';
      perf_fill_hold    : out std_logic := '0';
      perf_writeback    : out std_logic := '0';
      perf_way_slow     : out std_logic := '0';
      perf_wb_line      : out std_logic := '0';
      perf_fill_store   : out std_logic := '0';
      perf_fill_skip    : out std_logic := '0';
      perf_fill_absent  : out std_logic := '0';
      ra_request        : out std_logic := '0';
      ra_reqAddr        : out unsigned(31 downto 0) := (others => '0');
      ra_reqStream      : out std_logic := '0';
      ra_done           : in  std_logic := '0';
      ra_data           : in  std_logic_vector(255 downto 0) := (others => '0');
      ra_store          : in  std_logic := '0';
      ra_store_addr     : in  unsigned(31 downto 0) := (others => '0');
      ra_wr             : in  std_logic := '0';
      ra_chain_ok       : out std_logic := '0';
      ra_chain_addr     : out unsigned(31 downto 0) := (others => '0');
      ra_chain_sdram    : in  std_logic := '0';
      ra_chain_taken    : in  std_logic := '0';
      tail_q_ok         : in  std_logic := '0';
      perf_ra_issue     : out std_logic := '0';
      perf_ra_used      : out std_logic := '0'
   );
end entity;

architecture arch of cpu_datacache is

   signal ce_fetch         : std_logic;

   -- tags: 512 lines x {dirty, valid, PA(31:12)}
   signal tag_address_a    : std_logic_vector(8 downto 0) := (others => '0');
   signal tag_data_a       : std_logic_vector(21 downto 0) := (others => '0');
   signal tag_wren_a       : std_logic := '0';
   signal tag_address_b    : std_logic_vector(8 downto 0);
   signal tag_q_b          : std_logic_vector(21 downto 0);

   signal tag_newEna       : std_logic := '0';
   signal tag_newData      : std_logic_vector(21 downto 0);
   signal tag_compare      : std_logic_vector(21 downto 0);

   signal read_hit         : std_logic;

   signal tag_addr_1       : unsigned(31 downto 0) := (others => '0');
   signal tag_addr_low     : unsigned(3 downto 0) := (others => '0');
   signal tag_read_addr    : unsigned(12 downto 0) := (others => '0');
   signal fillAddr         : unsigned(31 downto 0) := (others => '0');
   signal rd_low           : unsigned(2 downto 0) := (others => '0');
   signal rd_sel           : unsigned(2 downto 0);

   -- data: 1024 qwords, port A fills (clk1x), port B the CPU (clk2x)
   signal fill_line        : unsigned(8 downto 0) := (others => '0');   -- line being filled
   signal fill_half        : std_logic := '0';                          -- its half of the 32-byte region
   signal fill_grant       : std_logic;
   signal fill_active_1x   : std_logic := '0';
   signal fill_beat_1x     : unsigned(1 downto 0) := (others => '0');
   signal fill_beat_now    : unsigned(1 downto 0);
   signal cache_addr_a     : std_logic_vector(9 downto 0);
   signal cache_wr_a       : std_logic;

   signal cache_address_b  : std_logic_vector(9 downto 0);
   signal cache_data_b     : std_logic_vector(63 downto 0);
   signal cache_we_b       : std_logic;
   signal cache_be_b       : std_logic_vector(7 downto 0);
   signal cache_q_b        : std_logic_vector(63 downto 0);

   signal write_be_rot     : std_logic_vector(7 downto 0);
   signal write_be_1       : std_logic_vector(7 downto 0);
   signal write_data_rot   : std_logic_vector(63 downto 0);
   signal write_data_1     : std_logic_vector(63 downto 0);

   type tState is
   (
      IDLE,
      CLEARCACHE,
      FILL,
      READWAIT,
      REREAD,
      WRITEBACK1ADDR,
      WRITEBACK1READ,
      WRITEBACK1WRITE,
      WRITEBACKBEATS,
      WRITEBACKDONE,
      COMMANDPROCESS,
      COMMANDDONE
   );
   signal state : tState := CLEARCACHE;

   -- As KI's cache ("LOADS WITHOUT THE BUBBLE", cpu_datacache_ki.vhd): in IDLE the data RAMs
   -- read the NEXT access's doubleword (tag_addr) while the pipeline moves, so a load answered
   -- in IDLE gets the read of the edge before. That read was not the load's own after a busy
   -- state (it read tag_read_addr) or a store (port b wrote): ram_stale. Such a load re-reads:
   -- READWAIT when the pipeline is stalled (the RAMs re-read tag_addr_1, its own doubleword,
   -- this cycle), else REREAD first (the RAMs read tag_read_addr, its own) and READWAIT next.
   signal ram_stale : std_logic := '1';
-- synthesis translate_off
   signal ram_rd_1  : std_logic_vector(9 downto 0) := (others => '0');
-- synthesis translate_on

   signal writeMode        : std_logic := '0';
   signal fillNext         : std_logic := '0';
   signal write_ena_1      : std_logic := '0';
   signal clearAddr        : std_logic_vector(8 downto 0) := (others => '0');
   signal isCommand        : std_logic := '0';

   signal tag_wren_cmd     : std_logic := '0';
   signal tag_addr_cmd     : std_logic_vector(8 downto 0) := (others => '0');
   signal tag_data_cmd     : std_logic_vector(21 downto 0) := (others => '0');

   -- write-back: the line's two qwords, then four beats of its 32-byte region
   signal wb_q0, wb_q1     : std_logic_vector(63 downto 0) := (others => '0');
   signal wb_beat          : unsigned(1 downto 0) := (others => '0');
   signal wb_base          : unsigned(31 downto 0) := (others => '0');

begin

   ce_fetch <= '1' when (stall = 0) else '0';

   ------------------ tags

   tag_wren_a     <= '1' when (tag_wren_cmd = '1') else
                     '1' when (state = IDLE and write_ena = '1' and read_hit = '1') else
                     '0';

   tag_address_a  <= tag_addr_cmd when (tag_wren_cmd = '1') else
                     std_logic_vector(tag_addr_1(12 downto 4));

   tag_data_a     <= tag_data_cmd when (tag_wren_cmd = '1') else
                     '1' & tag_compare(20 downto 0);

   itagram : entity mem.dpram
   generic map
   (
      addr_width  => 9,
      data_width  => 22 -- PA(31:12) + valid + dirty
   )
   port map
   (
      clock_a     => clk2x,
      address_a   => tag_address_a,
      data_a      => tag_data_a,
      wren_a      => tag_wren_a,

      clock_b     => clk2x,
      clken_b     => ce_fetch,
      address_b   => tag_address_b,
      data_b      => 22x"0",
      wren_b      => '0',
      q_b         => tag_q_b
   );

   tag_address_b <= std_logic_vector(tag_addr(12 downto 4));

   tag_compare   <= tag_newData when (tag_newEna = '1') else
                    tag_q_b;

   read_hit      <= '1' when (unsigned(tag_compare(19 downto 0)) = RW_addr(31 downto 12) and tag_compare(20) = '1') else '0';

   --------- fill (clk1x): the KI bridge returns the 32-byte region's four qwords in order from
   -- its start; qwords 2*fill_half and 2*fill_half+1 are this line's.

   fill_grant    <= ram_grant and ram_active;
   fill_beat_now <= (others => '0') when (fill_grant = '1') else fill_beat_1x;

   process (clk1x)
   begin
      if rising_edge(clk1x) then
         if (reset_1x = '1') then
            fill_active_1x <= '0';
            fill_beat_1x   <= (others => '0');
         elsif (fill_grant = '1') then
            fill_active_1x <= '1';
            fill_beat_1x   <= (others => '0');
            if (ddr3_DOUT_READY = '1') then
               fill_beat_1x <= 2x"1";
            end if;
         elsif (ram_active = '0') then
            fill_active_1x <= '0';
         elsif (fill_active_1x = '1' and ddr3_DOUT_READY = '1') then
            if (fill_beat_1x = 2x"3") then
               fill_active_1x <= '0';
            else
               fill_beat_1x <= fill_beat_1x + 1;
            end if;
         end if;
      end if;
   end process;

   cache_addr_a <= std_logic_vector(fill_line) & fill_beat_now(0);
   cache_wr_a   <= '1' when ((fill_active_1x = '1' or fill_grant = '1') and ddr3_DOUT_READY = '1' and
                             ram_active = '1' and fill_beat_now(1) = fill_half) else '0';

   gcache: for i in 0 to 7 generate
   begin
      icache: entity work.dpram
      generic map
      (
         addr_width  => 10,
         data_width  => 8
      )
      port map
      (
         clock_a     => clk1x,
         address_a   => cache_addr_a,
         data_a      => ddr3_DOUT(((i * 8) + 7) downto (i*8)),
         wren_a      => cache_wr_a,

         clock_b     => clk2x,
         address_b   => cache_address_b,
         data_b      => cache_data_b(((i * 8) + 7) downto (i*8)),
         wren_b      => cache_we_b and cache_be_b(i),
         q_b         => cache_q_b(((i * 8) + 7) downto (i*8))
      );
   end generate;

   cache_address_b <= std_logic_vector(tag_read_addr(12 downto 3)) when (state /= IDLE) else
                      std_logic_vector(tag_addr_1(12 downto 3)) when (ce_fetch = '0' or write_ena = '1') else
                      std_logic_vector(tag_addr(12 downto 3));

   -- Store data arrives in bits 31:0 (32-bit and smaller) or as a whole doubleword in bus order.
   little_endian_writes : if LITTLE_ENDIAN generate
      write_be_rot   <= write_be when (RW_64 = '1' or RW_addr(2) = '0') else
                        write_be(3 downto 0) & write_be(7 downto 4);
      write_data_rot <= write_data when (RW_64 = '1' or RW_addr(2) = '0') else
                        write_data(31 downto 0) & write_data(63 downto 32);
   end generate;

   big_endian_writes : if not LITTLE_ENDIAN generate
      write_be_rot   <= write_be when (RW_addr(2) = '0' and RW_64 = '0') else
                        write_be(3 downto 0) & write_be(7 downto 4);
      write_data_rot <= write_data when (RW_addr(2) = '0' and RW_64 = '0') else
                        write_data(31 downto 0) & write_data(63 downto 32);
   end generate;

   cache_data_b    <= write_data_1 when (stall4 = '1') else write_data_rot;
   cache_be_b      <= write_be_1   when (stall4 = '1') else write_be_rot;

   cache_we_b      <= '1' when ((state = IDLE and read_hit = '1' and write_ena = '1') or (writeMode = '1' and state = FILL and ram_done = '1')) else '0';

   write_done      <= '1' when ((state = IDLE and read_hit = '1' and write_ena = '1') or (writeMode = '1' and state = FILL and ram_done = '1')) else '0';

   read_busy       <= '1' when (state = READWAIT or state = REREAD or state = FILL) else '0';

   read_done       <= '1' when (state = IDLE and ram_stale = '0' and read_hit = '1' and read_ena = '1') else
                      '1' when (state = READWAIT) else
                      '1' when (writeMode = '0' and state = FILL and ram_done = '1') else
                      '0';

   -- A load answered outside IDLE may already see the next access's RW_addr.
   rd_sel          <= RW_addr(2 downto 0) when (state = IDLE) else rd_low;

   read_data       <= cache_q_b                        when (rd_sel = "000") else
                      8x"0"  & cache_q_b(63 downto  8) when (rd_sel = "001") else
                      16x"0" & cache_q_b(63 downto 16) when (rd_sel = "010") else
                      24x"0" & cache_q_b(63 downto 24) when (rd_sel = "011") else
                      32x"0" & cache_q_b(63 downto 32) when (rd_sel = "100") else
                      40x"0" & cache_q_b(63 downto 40) when (rd_sel = "101") else
                      48x"0" & cache_q_b(63 downto 48) when (rd_sel = "110") else
                      56x"0" & cache_q_b(63 downto 56);

   -- The access's qword arrives last of the four beats: cpu.vhd holds ram_done a cycle.
   fill_last_q     <= '1' when (tag_read_addr(4 downto 3) = "11") else '0';

   clear_busy      <= '1' when (state = CLEARCACHE) else '0';
   wb_hold         <= '0';

   CachecommandStall <= '1' when (CacheCommandEna = '1' and CacheCommand = 5x"01") else
                        '1' when (CacheCommandEna = '1' and CacheCommand = 5x"05") else
                        '1' when (CacheCommandEna = '1' and CacheCommand = 5x"09") else
                        '1' when (CacheCommandEna = '1' and CacheCommand = 5x"0D") else
                        '1' when (CacheCommandEna = '1' and CacheCommand = 5x"11") else
                        '1' when (CacheCommandEna = '1' and CacheCommand = 5x"15") else
                        '1' when (CacheCommandEna = '1' and CacheCommand = 5x"19") else
                        '0';

   process (clk2x)
   begin
      if rising_edge(clk2x) then

         ram_request       <= '0';
         writeback_ena     <= '0';
         CachecommandDone  <= '0';
         tag_wren_cmd      <= '0';
         writeTagEna       <= '0';

         if (ce_fetch = '1') then
            tag_addr_1   <= tag_addr;
            tag_newEna   <= '0';
            if (tag_wren_a = '1') then
               tag_newData  <= tag_data_a;
               if (tag_address_a = std_logic_vector(tag_addr(12 downto 4))) then
                  tag_newEna   <= '1';
               end if;
            end if;
         else
            if (tag_wren_a = '1') then
               tag_newData  <= tag_data_a;
               if (tag_address_a = std_logic_vector(tag_addr_1(12 downto 4))) then
                  tag_newEna   <= '1';
               end if;
            end if;
         end if;

-- synthesis translate_off
         -- KI's checks: every load answered from the data RAMs gets the doubleword they read on
         -- the previous edge - in IDLE tag_addr_1's, in READWAIT tag_read_addr's.
         ram_rd_1 <= cache_address_b;
         if (reset_2x = '0' and read_done = '1' and state = IDLE and
             ram_rd_1 /= std_logic_vector(tag_addr_1(12 downto 3))) then
            report "cpu_datacache: a load hit in IDLE on a data RAM read of another doubleword"
               severity failure;
         end if;
         if (reset_2x = '0' and read_done = '1' and state = READWAIT and
             ram_rd_1 /= std_logic_vector(tag_read_addr(12 downto 3))) then
            report "cpu_datacache: a load answered from a data RAM read of another doubleword"
               severity failure;
         end if;
-- synthesis translate_on

         -- A busy cycle's RAM read was tag_read_addr; the access after it re-reads (ram_stale).
         if (state /= IDLE) then
            ram_stale <= '1';
         end if;

         if (reset_2x = '1') then
            state          <= CLEARCACHE;
            clearAddr      <= (others => '0');
            ram_stale      <= '1';
         else

            case(state) is

               when IDLE =>
                  -- a store writes port b this cycle, so the RAMs read nothing for the next access
                  ram_stale      <= write_ena;
                  writeMode      <= write_ena;
                  write_be_1     <= write_be_rot;
                  write_data_1   <= write_data_rot;
                  fillNext       <= '0';
                  write_ena_1    <= write_ena;
                  rd_low         <= RW_addr(2 downto 0);
                  fillAddr       <= unsigned(tag_compare(19 downto 0)) & RW_addr(11 downto 4) & "0000";
                  tag_addr_low   <= tag_addr_1(3 downto 0);
                  tag_read_addr  <= tag_addr_1(12 downto 0);
                  fill_line      <= tag_addr_1(12 downto 4);
                  fill_half      <= RW_addr(4);
                  isCommand      <= '0';
                  -- The KI memory path fetches the whole 32-byte region.
                  ram_reqAddr    <= RW_addr(31 downto 5) & "00000";
                  tag_data_cmd   <= write_ena & '1' & std_logic_vector(RW_addr(31 downto 12)); -- default for fill
                  tag_addr_cmd   <= std_logic_vector(tag_addr_1(12 downto 4));
                  wb_base        <= unsigned(tag_compare(19 downto 0)) & RW_addr(11 downto 4) & "0000";

                  if ((read_ena = '1' or write_ena = '1') and read_hit = '0') then
                     if (tag_compare(21) = '1') then
                        state          <= WRITEBACK1ADDR;
                        tag_read_addr(3 downto 0) <= "0000";
                        fillNext       <= '1';
                     else
                        state          <= FILL;
                        ram_request    <= '1';
                     end if;

                  elsif (ram_stale = '1' and read_ena = '1' and read_hit = '1') then
                     state <= READWAIT;
                     if (ce_fetch = '1') then
                        state <= REREAD;
                     end if;

                  elsif (CacheCommandEna = '1') then
                     state          <= COMMANDPROCESS;
                     isCommand      <= '1';
                     tag_read_addr(3 downto 0) <= "0000";
                     writeTagValue  <= tag_compare(20) & tag_compare(21) & unsigned(tag_compare(19 downto 0)); -- valid & dirty & 20 bit address

                     case (CacheCommand) is

                        when 5x"01" => -- index write back invalidate
                           if (tag_compare(21 downto 20) = "11") then
                              state          <= WRITEBACK1ADDR;
                           end if;
                           tag_wren_cmd    <= '1';
                           tag_data_cmd    <= "00" & tag_compare(19 downto 0);

                        when 5x"05" => -- index load tag
                           writeTagEna <= '1';

                        when 5x"09" => -- index store tag
                           tag_wren_cmd    <= '1';
                           tag_data_cmd    <= TagLo_Dirty & TagLo_Valid & std_logic_vector(TagLo_Addr);

                        when 5x"0D" => -- create dirty exclusive
                           if (tag_compare(21) = '1' and (tag_compare(20) = '0' or unsigned(tag_compare(19 downto 0)) /= RW_addr(31 downto 12))) then
                              state          <= WRITEBACK1ADDR;
                           end if;
                           tag_wren_cmd    <= '1';
                           tag_data_cmd    <= "11" & std_logic_vector(RW_addr(31 downto 12));

                        when 5x"11" => -- hit invalidate
                           if (read_hit = '1') then
                              tag_wren_cmd    <= '1';
                              tag_data_cmd    <= "00" & tag_compare(19 downto 0);
                           end if;

                        when 5x"15" => -- hit write back invalidate
                           if (read_hit = '1') then
                              if (tag_compare(21) = '1') then
                                 state          <= WRITEBACK1ADDR;
                              end if;
                              tag_wren_cmd    <= '1';
                              tag_data_cmd    <= "00" & tag_compare(19 downto 0);
                           end if;

                        when 5x"19" => -- hit write back
                           if (read_hit = '1' and tag_compare(21) = '1') then
                              state          <= WRITEBACK1ADDR;
                              tag_wren_cmd   <= '1';
                              tag_data_cmd   <= "01" & tag_compare(19 downto 0);
                           end if;

                        when others => state <= IDLE;
                     end case;

                  end if;

               when CLEARCACHE =>
                  tag_wren_cmd <= '1';
                  tag_addr_cmd <= clearAddr;
                  tag_data_cmd <= (others => '0');
                  if (clearAddr /= 9x"1FF") then
                     clearAddr <= std_logic_vector(unsigned(clearAddr) + 1);
                  else
                     state     <= IDLE;
                  end if;

               when FILL =>
                  if (ram_request = '1') then
                     tag_wren_cmd   <= '1';
                  end if;
                  if (ram_done = '1') then
                     state          <= IDLE;
                  end if;

               when READWAIT =>
                  state <= IDLE;

               -- The data RAMs read tag_read_addr, the load's own doubleword; READWAIT delivers it.
               when REREAD =>
                  state <= READWAIT;

               -- Write-back: read the line's two qwords (the data RAM read is registered), then
               -- send the 32-byte region as four beats, this line's two in place.
               when WRITEBACK1ADDR =>
                  if (fifo_block = '0') then
                     state <= WRITEBACK1READ;
                  end if;

               when WRITEBACK1READ =>
                  state            <= WRITEBACK1WRITE;
                  tag_read_addr(3) <= '1';

               when WRITEBACK1WRITE =>
                  state            <= WRITEBACKBEATS;
                  wb_q0            <= cache_q_b;
                  wb_beat          <= (others => '0');

               when WRITEBACKBEATS =>
                  if (wb_beat = 0) then
                     wb_q1 <= cache_q_b;
                  end if;
                  writeback_ena  <= '1';
                  writeback_addr <= wb_base(31 downto 5) & wb_beat & "000";
                  if (wb_beat(1) /= wb_base(4)) then
                     writeback_data <= (others => '0');      -- not this line's: masked off
                  elsif (wb_beat(0) = '0') then
                     writeback_data <= wb_q0;
                  elsif (wb_beat = 0) then
                     writeback_data <= cache_q_b;
                  else
                     writeback_data <= wb_q1;
                  end if;
                  if (wb_base(4) = '0') then
                     writeback_mask  <= "0011";
                     writeback_bytes <= x"0000FFFF";
                  else
                     writeback_mask  <= "1100";
                     writeback_bytes <= x"FFFF0000";
                  end if;
                  wb_beat <= wb_beat + 1;
                  if (wb_beat = 3) then
                     state <= WRITEBACKDONE;
                  end if;

               when WRITEBACKDONE =>
                  tag_read_addr(3 downto 0) <= tag_addr_low;
                  if (fifo_block = '0') then
                     fillNext <= '0';
                     if (fillNext = '1') then
                        state       <= FILL;
                        ram_request <= '1';
                     else
                        state             <= IDLE;
                        CachecommandDone  <= isCommand;
                     end if;
                  end if;

               when COMMANDPROCESS =>
                  state <= COMMANDDONE;

               when COMMANDDONE =>
                  state             <= IDLE;
                  CachecommandDone  <= '1';

            end case;

         end if;

      end if;
   end process;


-- synthesis translate_off
   -- Simulation-only consistency check (v0.7.0 bring-up). A shadow of RAM's first 16 MiB as
   -- the CPU must see it: learnt from fills, updated by every cached store. Every load the cache
   -- answers is compared with it (failure), every write-back (failure) and every fill (note: an
   -- uncached store or a DMA write changes RAM behind the cache legitimately). A hit
   -- invalidate or create-dirty-exclusive forgets its line. Bytes are in bus (address) order.
   process (clk1x, clk2x)
      type t_shadow is array (0 to 16777215) of integer range -1 to 255;
      variable sh   : t_shadow := (others => -1);
      variable st_a : unsigned(31 downto 0) := (others => '0');
      variable ld_a : unsigned(31 downto 0) := (others => '0');
      variable a    : unsigned(31 downto 0);
      variable b, v : integer;
   begin
      if rising_edge(clk1x) then
         if (cache_wr_a = '1' and ram_reqAddr(28 downto 24) = "00000") then
            b := to_integer(ram_reqAddr(23 downto 5)) * 32 + to_integer(fill_beat_now) * 8;
            for i in 0 to 7 loop
               v := to_integer(unsigned(ddr3_DOUT(i * 8 + 7 downto i * 8)));
               if (sh(b + i) /= -1 and sh(b + i) /= v) then
                  report "dcache check: FILL of " & to_hstring(to_unsigned(b + i, 32)) & " brings " &
                         to_hstring(to_unsigned(v, 8)) & ", shadow " & to_hstring(to_unsigned(sh(b + i), 8)) severity note;
               end if;
               sh(b + i) := v;
            end loop;
         end if;
      end if;
      if rising_edge(clk2x) and reset_2x = '0' then
         -- stores into the data RAMs
         if (cache_we_b = '1') then
            if (state = IDLE) then a := RW_addr; else a := st_a; end if;
            if (a(28 downto 24) = "00000") then
               b := to_integer(a(23 downto 3)) * 8;
               for i in 0 to 7 loop
                  if (cache_be_b(i) = '1') then sh(b + i) := to_integer(unsigned(cache_data_b(i * 8 + 7 downto i * 8))); end if;
               end loop;
            end if;
         end if;
         -- loads answered
         if (read_done = '1') then
            if (state = IDLE) then a := RW_addr; else a := ld_a; end if;
            if (a(28 downto 24) = "00000") then
               b := to_integer(a(23 downto 3)) * 8;
               for i in 0 to 7 loop
                  v := to_integer(unsigned(cache_q_b(i * 8 + 7 downto i * 8)));
                  assert (sh(b + i) = -1 or sh(b + i) = v)
                     report "dcache check: LOAD of " & to_hstring(a) & " in state " & tState'image(state) &
                            " byte " & integer'image(i) & " got " & to_hstring(to_unsigned(v, 8)) &
                            " expected " & to_hstring(to_unsigned(sh(b + i), 8)) severity failure;
               end loop;
            end if;
         end if;
         -- write-backs
         if (writeback_ena = '1' and writeback_addr(28 downto 24) = "00000" and
             writeback_mask(to_integer(writeback_addr(4 downto 3))) = '1') then
            b := to_integer(writeback_addr(23 downto 3)) * 8;
            for i in 0 to 7 loop
               v := to_integer(unsigned(writeback_data(i * 8 + 7 downto i * 8)));
               assert (sh(b + i) = -1 or sh(b + i) = v)
                  report "dcache check: WRITE-BACK of " & to_hstring(writeback_addr) & " byte " & integer'image(i) &
                         " writes " & to_hstring(to_unsigned(v, 8)) & " expected " & to_hstring(to_unsigned(sh(b + i), 8)) severity failure;
            end loop;
         end if;
         -- commands that drop a line's data
         if (state = IDLE and CacheCommandEna = '1' and RW_addr(28 downto 24) = "00000" and
             ((CacheCommand = 5x"11" and read_hit = '1') or CacheCommand = 5x"0D")) then
            b := to_integer(RW_addr(23 downto 4)) * 16;
            for i in 0 to 15 loop sh(b + i) := -1; end loop;
         end if;
         if (state = IDLE and write_ena = '1') then st_a := RW_addr; end if;
         if (state = IDLE and read_ena = '1') then ld_a := RW_addr; end if;
      end if;
   end process;
-- synthesis translate_on

end architecture;
