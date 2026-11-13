-- Verilator system simulation (sim/vl): stand-ins for rtl/r4k's Altera RAM wrappers
-- (RamMLAB.vhd, dpram.vhd). Each instantiates an unbound component, which `ghdl --synth`
-- leaves as a black box; sim/vl/ram_models.v holds the Verilog models of those boxes.
library ieee;
use ieee.std_logic_1164.all;

entity RamMLAB is
   generic (width : natural; width_byteena : natural := 1; widthad : natural);
   port (
      inclock   : in std_logic;
      wren      : in std_logic;
      data      : in std_logic_vector(width-1 downto 0);
      wraddress : in std_logic_vector(widthad-1 downto 0);
      rdaddress : in std_logic_vector(widthad-1 downto 0);
      q         : out std_logic_vector(width-1 downto 0));
end;

architecture rtl of RamMLAB is
   component sim_ram_mlab is
      generic (width : natural; widthad : natural);
      port (
         inclock   : in std_logic;
         wren      : in std_logic;
         data      : in std_logic_vector(width-1 downto 0);
         wraddress : in std_logic_vector(widthad-1 downto 0);
         rdaddress : in std_logic_vector(widthad-1 downto 0);
         q         : out std_logic_vector(width-1 downto 0));
   end component;
begin
   u : sim_ram_mlab generic map (width => width, widthad => widthad)
      port map (inclock => inclock, wren => wren, data => data, wraddress => wraddress, rdaddress => rdaddress, q => q);
end;

library ieee;
use ieee.std_logic_1164.all;

entity dpram is
   generic (addr_width : integer := 8; data_width : integer := 8);
   port (
      clock_a   : in std_logic;
      clken_a   : in std_logic := '1';
      address_a : in std_logic_vector(addr_width-1 downto 0);
      data_a    : in std_logic_vector(data_width-1 downto 0);
      wren_a    : in std_logic := '0';
      q_a       : out std_logic_vector(data_width-1 downto 0);
      clock_b   : in std_logic;
      clken_b   : in std_logic := '1';
      address_b : in std_logic_vector(addr_width-1 downto 0);
      data_b    : in std_logic_vector(data_width-1 downto 0) := (others => '0');
      wren_b    : in std_logic := '0';
      q_b       : out std_logic_vector(data_width-1 downto 0));
end;

architecture syn of dpram is
   component sim_dpram is
      generic (addr_width_a : integer; data_width_a : integer; addr_width_b : integer; data_width_b : integer);
      port (
         clock_a   : in std_logic;
         clken_a   : in std_logic;
         address_a : in std_logic_vector(addr_width_a-1 downto 0);
         data_a    : in std_logic_vector(data_width_a-1 downto 0);
         wren_a    : in std_logic;
         q_a       : out std_logic_vector(data_width_a-1 downto 0);
         clock_b   : in std_logic;
         clken_b   : in std_logic;
         address_b : in std_logic_vector(addr_width_b-1 downto 0);
         data_b    : in std_logic_vector(data_width_b-1 downto 0);
         wren_b    : in std_logic;
         q_b       : out std_logic_vector(data_width_b-1 downto 0));
   end component;
begin
   u : sim_dpram generic map (addr_width_a => addr_width, data_width_a => data_width, addr_width_b => addr_width, data_width_b => data_width)
      port map (clock_a => clock_a, clken_a => clken_a, address_a => address_a, data_a => data_a, wren_a => wren_a, q_a => q_a,
                clock_b => clock_b, clken_b => clken_b, address_b => address_b, data_b => data_b, wren_b => wren_b, q_b => q_b);
end;

library ieee;
use ieee.std_logic_1164.all;

entity dpram_dif is
   generic (addr_width_a : integer := 8; data_width_a : integer := 8; addr_width_b : integer := 8; data_width_b : integer := 8);
   port (
      clock_a   : in  std_logic;
      address_a : in  std_logic_vector(addr_width_a-1 downto 0);
      data_a    : in  std_logic_vector(data_width_a-1 downto 0) := (others => '0');
      clken_a   : in  std_logic := '1';
      wren_a    : in  std_logic := '0';
      q_a       : out std_logic_vector(data_width_a-1 downto 0);
      cs_a      : in  std_logic := '1';
      clock_b   : in  std_logic;
      address_b : in  std_logic_vector(addr_width_b-1 downto 0) := (others => '0');
      data_b    : in  std_logic_vector(data_width_b-1 downto 0) := (others => '0');
      clken_b   : in  std_logic := '1';
      wren_b    : in  std_logic := '0';
      q_b       : out std_logic_vector(data_width_b-1 downto 0);
      cs_b      : in  std_logic := '1');
end;

architecture syn of dpram_dif is
   component sim_dpram is
      generic (addr_width_a : integer; data_width_a : integer; addr_width_b : integer; data_width_b : integer);
      port (
         clock_a   : in std_logic;
         clken_a   : in std_logic;
         address_a : in std_logic_vector(addr_width_a-1 downto 0);
         data_a    : in std_logic_vector(data_width_a-1 downto 0);
         wren_a    : in std_logic;
         q_a       : out std_logic_vector(data_width_a-1 downto 0);
         clock_b   : in std_logic;
         clken_b   : in std_logic;
         address_b : in std_logic_vector(addr_width_b-1 downto 0);
         data_b    : in std_logic_vector(data_width_b-1 downto 0);
         wren_b    : in std_logic;
         q_b       : out std_logic_vector(data_width_b-1 downto 0));
   end component;
   signal q0 : std_logic_vector(data_width_a-1 downto 0);
   signal q1 : std_logic_vector(data_width_b-1 downto 0);
   signal wa, wb : std_logic;
begin
   q_a <= q0 when cs_a = '1' else (others => '1');
   q_b <= q1 when cs_b = '1' else (others => '1');
   wa  <= wren_a and cs_a;
   wb  <= wren_b and cs_b;
   u : sim_dpram generic map (addr_width_a => addr_width_a, data_width_a => data_width_a, addr_width_b => addr_width_b, data_width_b => data_width_b)
      port map (clock_a => clock_a, clken_a => clken_a, address_a => address_a, data_a => data_a, wren_a => wa, q_a => q0,
                clock_b => clock_b, clken_b => clken_b, address_b => address_b, data_b => data_b, wren_b => wb, q_b => q1);
end;
