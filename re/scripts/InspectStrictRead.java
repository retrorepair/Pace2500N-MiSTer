// Targeted disassembly of the first unknown NEC MMIO read, original U202.
// @category Pace
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.lang.Register;
import ghidra.program.model.data.UnsignedIntegerDataType;
import ghidra.program.model.symbol.SourceType;
import java.math.BigInteger;
import java.io.PrintWriter;

public class InspectStrictRead extends GhidraScript {
    public void run() throws Exception {
        Address start=toAddr(0xbfc01e18L), end=toAddr(0xbfc01fffL);
        Register mode=currentProgram.getRegister("ISA_MODE");
        if(mode==null) throw new Exception("Missing MIPS ISA_MODE context register");
        if(getInstructionAt(start)==null)
            currentProgram.getProgramContext().setValue(mode,start,end,BigInteger.ONE);
        disassemble(start);
        Function fn=getFunctionAt(start);
        if(fn==null) fn=createFunction(start,"boot_read_unknown_nec_register");
        if(fn!=null) fn.setReturnType(UnsignedIntegerDataType.dataType,SourceType.USER_DEFINED);
        disassemble(toAddr(0xbfc00570L));
        try(PrintWriter out=new PrintWriter(getScriptArgs()[0])) {
            out.println("Original FLASH_U202.bin, base BFC00000, MIPS big endian, ISA_MODE=1 (MIPS16e).");
            out.println("This is static disassembly, not an identification of NEC registers.");
            InstructionIterator instructions=currentProgram.getListing().getInstructions(new AddressSet(start,end),true);
            while(instructions.hasNext()) {
                Instruction ins=instructions.next();
                out.println(ins.getAddress()+"  "+ins.toString());
            }
            out.println("\nMIPS32 caller around JALX:");
            instructions=currentProgram.getListing().getInstructions(new AddressSet(toAddr(0xbfc00570L),toAddr(0xbfc00680L)),true);
            while(instructions.hasNext()) {
                Instruction ins=instructions.next();
                out.println(ins.getAddress()+"  "+ins.toString());
            }
            if(fn!=null) {
                DecompInterface decomp=new DecompInterface();
                try {
                    decomp.openProgram(currentProgram);
                    DecompileResults result=decomp.decompileFunction(fn,30,monitor);
                    out.println("\nDECOMPILATION (approximate types/register semantics):");
                    if(result.decompileCompleted()) out.println(result.getDecompiledFunction().getC());
                    else out.println(result.getErrorMessage());
                } finally { decomp.dispose(); }
            }
        }
    }
}
