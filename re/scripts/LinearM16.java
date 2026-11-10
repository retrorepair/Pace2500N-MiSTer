// @category Pace
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.lang.*;
import ghidra.program.disassemble.*;
import java.math.BigInteger;
import java.io.PrintWriter;
// Read-only linear MIPS16 sweep (no flow following): args out, then start:end pairs (hex).
public class LinearM16 extends GhidraScript {
    public void run() throws Exception {
        String[] args=getScriptArgs();
        Register isa=currentProgram.getRegister("ISA_MODE");
        try(PrintWriter out=new PrintWriter(args[0])) {
          for(int i=1;i<args.length;i++){
            String[] p=args[i].split(":");
            Address a=toAddr(Long.parseUnsignedLong(p[0],16)),end=toAddr(Long.parseUnsignedLong(p[1],16));
            BigInteger mode=p.length>2?new BigInteger(p[2]):BigInteger.ONE;
            out.println("; range "+a+" .. "+end+" ISA_MODE="+mode);
            clearListing(a,end);
            currentProgram.getProgramContext().setValue(isa,a,end,mode);
            while(a.compareTo(end)<0){
                Disassembler d=Disassembler.getDisassembler(currentProgram,monitor,null);
                d.disassemble(a,new AddressSet(a,a.add(3)),false);
                Instruction ins=getInstructionAt(a);
                if(ins==null){out.println(a+"  .half "+String.format("%04x",getShort(a)&0xffff));a=a.add(2);continue;}
                StringBuilder s=new StringBuilder(a+"  "+ins);
                for(ghidra.program.model.symbol.Reference r:ins.getReferencesFrom()){
                    if(r.getReferenceType().isData()){
                        try{s.append("   ; ["+r.getToAddress()+"]="+String.format("%08x",getInt(r.getToAddress())));}catch(Exception e){}
                    }
                }
                out.println(s);
                a=a.add(ins.getLength());
            }
          }
        }
    }
}
