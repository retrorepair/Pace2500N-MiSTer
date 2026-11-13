-- The vendored CPU as the Pace's NEC VR4110: big-endian, 32-bit addressing, no FPU traps, no
-- address-error exceptions (the firmware makes no misaligned accesses; the proven multi-cycle
-- CPU halted on them), Count at COUNT_NUM/COUNT_DEN of clk2x. Integer-only generics so the
-- SystemVerilog top (rtl/pace_r4k.sv) can instantiate it.
library IEEE;
use IEEE.std_logic_1164.all;
use IEEE.numeric_std.all;

entity pace_r4k_core is
   generic
   (
      COUNT_NUM : integer := 27;
      COUNT_DEN : integer := 100
   );
   port
   (
      clk1x, clk2x, reset_1x, reset_2x : in std_logic;
      irq            : in  std_logic;
      mem_request    : out std_logic;
      mem_rnw        : out std_logic;
      mem_address    : out std_logic_vector(31 downto 0);
      mem_req64      : out std_logic;
      mem_size       : out std_logic_vector(2 downto 0);
      mem_writeMask  : out std_logic_vector(7 downto 0);
      mem_dataWrite  : out std_logic_vector(63 downto 0);
      mem_line_write : out std_logic;
      mem_line_data  : out std_logic_vector(255 downto 0);
      mem_line_bytes : out std_logic_vector(31 downto 0);
      mem_dataRead   : in  std_logic_vector(63 downto 0);
      mem_done       : in  std_logic;
      grant          : in  std_logic;
      dout           : in  std_logic_vector(63 downto 0);
      dout_ready     : in  std_logic;
      ckpt_valid     : in  std_logic;
      ckpt_wr        : in  std_logic;
      ckpt_index     : in  std_logic_vector(6 downto 0);
      ckpt_data      : in  std_logic_vector(31 downto 0);
      errors         : out std_logic_vector(5 downto 0);
      fetch_pc       : out std_logic_vector(31 downto 0);
      retired        : out std_logic_vector(31 downto 0);
      perf           : out std_logic_vector(11 downto 0);   -- diagnostics: KI lost-cycle census
      cause          : out std_logic_vector(31 downto 0);   -- diagnostics: live Cause/Status bits
      epc            : out std_logic_vector(31 downto 0);   -- diagnostics: live EPC
      badvaddr       : out std_logic_vector(31 downto 0);   -- diagnostics: live BadVAddr
      wb_valid       : out std_logic;                       -- diagnostics: retiring instruction
      wb_pc          : out std_logic_vector(31 downto 0);
      wb_rd          : out std_logic_vector(5 downto 0);
      wb_data        : out std_logic_vector(31 downto 0)
   );
end entity;

architecture rtl of pace_r4k_core is
   signal address_u : unsigned(31 downto 0);
   signal size_u    : unsigned(2 downto 0);
begin
   mem_address <= std_logic_vector(address_u);
   mem_size    <= std_logic_vector(size_u);

   core : entity work.cpu
   generic map
   (
      LITTLE_ENDIAN        => false,
      ADDR32_ONLY          => true,
      NO_TRAP_INSTR        => false,
      INSTR_KSEG_ONLY      => false,
      FPU_CVT_L_NARROW     => true,
      NO_ADDRESS_ERROR     => true,
      NO_FPU_EXCEPTION     => true,
      COUNT_NUM            => COUNT_NUM,
      COUNT_DEN            => COUNT_DEN
   )
   port map
   (
      clk1x                 => clk1x,
      clk2x                 => clk2x,
      reset_1x              => reset_1x,
      reset_2x              => reset_2x,
      DATACACHEWRITETHROUGH => '0',
      irqRequest            => '0' & irq,
      cpuPaused             => '0',
      error_instr           => errors(0),
      error_stall           => errors(1),
      error_FPU             => errors(2),
      error_exception       => errors(3),
      error_fifo            => errors(4),
      error_TLB             => errors(5),
      debug_fetch_pc        => fetch_pc,
      debug_retired         => retired,
      debug_retire_pc       => open,
      debug_retire_opcode   => open,
      debug_cop0_cause_live => cause,
      debug_cop0_epc_live   => epc,
      debug_cop0_badvaddr_live => badvaddr,
      debug_wb_valid        => wb_valid,
      debug_wb_pc           => wb_pc,
      debug_wb_rd           => wb_rd,
      debug_wb_data         => wb_data,
      debug_perf_events     => perf,
      mem_request           => mem_request,
      mem_rnw               => mem_rnw,
      mem_address           => address_u,
      mem_req64             => mem_req64,
      mem_size              => size_u,
      mem_writeMask         => mem_writeMask,
      mem_dataWrite         => mem_dataWrite,
      mem_line_write        => mem_line_write,
      mem_line_ra           => open,
      mem_line_data         => mem_line_data,
      mem_line_bytes        => mem_line_bytes,
      mem_dataRead          => mem_dataRead,
      mem_done              => mem_done,
      rdram_granted2x       => grant,
      ddr3_DOUT             => dout,
      ddr3_DOUT_READY       => dout_ready,
      fast_ok               => '0',
      fast_req_tog          => open,
      fast_req_line         => open,
      fast_req_stream       => open,
      ckpt_valid            => ckpt_valid,
      ckpt_wr               => ckpt_wr,
      ckpt_index            => unsigned(ckpt_index),
      ckpt_data             => ckpt_data
   );
end architecture;
