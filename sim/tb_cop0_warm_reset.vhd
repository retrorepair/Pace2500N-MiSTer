-- A pending exception must never survive a CPU reset, even while the
-- pipeline is stalled. Cold power-up alone leaves this defect unexercised.
library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.env.all;
entity tb_cop0_warm_reset is end;
architecture test of tb_cop0_warm_reset is
    signal clk : std_logic := '0';
    signal reset : std_logic := '1';
    signal stall : unsigned(4 downto 0) := (others => '0');
    signal decode_irq : std_logic := '0';
    signal exception, exception_stage1 : std_logic;
begin
    clk <= not clk after 5 ns;
    dut : entity work.cpu_cop0
        generic map (ADDR32_ONLY => true, NO_ADDRESS_ERROR => true)
        port map (
            clk2x => clk,
            stall => stall,
            stall4Masked => (others => '0'),
            executeNew => '0',
            reset => reset,
            cpuPaused => '0',
            error_exception => open,
            error_TLB => open,
            irqRequest => (others => '0'),
            irqTrigger => open,
            decode_irq => decode_irq,
            cop0_export => open,
            debug_cause => open,
            debug_epc => open,
            debug_badvaddr => open,
            eret => '0',
            exception3 => '0',
            exceptionNewPC => '0',
            exceptionPCStore => (others => '0'),
            exceptionFPU => '0',
            exceptionCode_1 => (others => '0'),
            exceptionCode_3 => (others => '0'),
            exception_COP => (others => '0'),
            isDelaySlot => '0',
            ckpt_we => '0',
            ckpt_index => (others => '0'),
            ckpt_value => (others => '0'),
            delaySlotJumpPC => (others => '0'),
            chainedDelaySlot => '0',
            nextDelaySlot => '0',
            pcOld1 => x"FFFFFFFF9FC11161",
            eretPC => open,
            exceptionPC => open,
            exception => exception,
            exceptionStage1 => exception_stage1,
            COP0_enable => open,
            COP1_enable => open,
            COP2_enable => open,
            fpuRegMode => open,
            privilegeMode => open,
            kusegUnmapped => open,
            bit64region => open,
            writeEnable => '0',
            regIndex => (others => '0'),
            writeValue => (others => '0'),
            readValue => open,
            executeSetLL => '0',
            executeLLfromTLB => '0',
            executeLLAddr => (others => '0'),
            TagLo_Valid => open,
            TagLo_Dirty => open,
            TagLo_Addr => open,
            writeDatacacheTagEna => '0',
            writeDatacacheTagValue => (others => '0'),
            TLBR => '0',
            TLBWI => '0',
            TLBWR => '0',
            TLBP => '0',
            TLBDone => open,
            TLB_instrReq => '0',
            TLB_ss_load => '0',
            TLB_instrAddrIn => (others => '0'),
            TLB_instrUseCache => open,
            TLB_instrStall => open,
            TLB_instrUnStall => open,
            TLB_instrAddrOutFound => open,
            TLB_instrAddrOutLookup => open,
            TLB_dataReq => '0',
            TLB_dataIsWrite => '0',
            TLB_dataAddrIn => (others => '0'),
            TLB_dataUseCacheFound => open,
            TLB_dataUseCacheLookup => open,
            TLB_dataStall => open,
            TLB_dataUnStall => open,
            TLB_dataAddrOutFound => open,
            TLB_dataAddrOutLookup => open,
            kseg0_uncached => open
        );
    process
    begin
        wait until falling_edge(clk); reset <= '0'; decode_irq <= '1';
        wait until rising_edge(clk); wait for 1 ns;
        assert exception = '1' report "Test did not create a pending interrupt exception" severity failure;
        wait until falling_edge(clk);
        decode_irq <= '0'; stall <= (others => '1'); reset <= '1';
        wait until rising_edge(clk); wait for 1 ns;
        assert exception = '0' and exception_stage1 = '0'
            report "Warm reset retained a pending exception while stalled" severity failure;
        wait until falling_edge(clk); reset <= '0';
        for i in 1 to 4 loop
            wait until rising_edge(clk); wait for 1 ns;
            assert exception = '0' and exception_stage1 = '0'
                report "Pre-reset exception reappeared before first fetch" severity failure;
        end loop;
        report "PASS: pending interrupt exception cancelled by warm reset, including stalled restart";
        finish;
    end process;
end architecture;
