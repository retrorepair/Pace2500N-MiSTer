// @category Pace
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import java.math.BigInteger;
import java.io.PrintWriter;
public class InspectShift extends GhidraScript {
    public void run() throws Exception {
        Address start=toAddr(0xbfc0b2ceL),end=toAddr(0xbfc0b330L);
        if(getInstructionAt(start)==null)
            currentProgram.getProgramContext().setValue(currentProgram.getRegister("ISA_MODE"),start,end,BigInteger.ONE);
        disassemble(start);
        try(PrintWriter out=new PrintWriter(getScriptArgs()[0])) {
            out.println("Static MIPS16 disassembly at the experimental zero-MMIO probe endpoint.");
            InstructionIterator it=currentProgram.getListing().getInstructions(new AddressSet(start,end),true);
            while(it.hasNext()) {
                Instruction ins=it.next();
                out.println(ins.getAddress()+"  "+ins);
            }
        }
    }
}
