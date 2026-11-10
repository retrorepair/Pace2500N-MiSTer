// @category Pace
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import java.math.BigInteger;
import java.io.PrintWriter;
public class InspectRange extends GhidraScript {
    public void run() throws Exception {
        String[] args=getScriptArgs();
        Address start=toAddr(Long.parseUnsignedLong(args[0],16)),end=toAddr(Long.parseUnsignedLong(args[1],16));
        if(args.length>4 && args[4].equals("redecode"))clearListing(start,end);
        if(getInstructionAt(start)==null)
            currentProgram.getProgramContext().setValue(currentProgram.getRegister("ISA_MODE"),start,end,args.length>3?new BigInteger(args[3]):BigInteger.ONE);
        disassemble(start);
        try(PrintWriter out=new PrintWriter(args[2])) {
            InstructionIterator it=currentProgram.getListing().getInstructions(new AddressSet(start,end),true);
            while(it.hasNext()) { Instruction ins=it.next();out.println(ins.getAddress()+"  "+ins); }
        }
    }
}
