// @category Pace
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import java.io.PrintWriter;
public class DecompileTargets extends GhidraScript {
 public void run() throws Exception {
  String[] args=getScriptArgs();DecompInterface d=new DecompInterface();
  d.openProgram(currentProgram);
  try(PrintWriter out=new PrintWriter(args[0])) {
   for(int i=1;i<args.length;i++) {
    String[] pair=args[i].split(":");
    ghidra.program.model.address.Address a=toAddr(Long.parseUnsignedLong(pair[0],16));
    Function f=getFunctionAt(a);
    if(f==null)f=createFunction(a,pair.length>1?pair[1]:null);
    if(f==null){out.println("No function at "+a);continue;}
    if(pair.length>1)f.setName(pair[1],ghidra.program.model.symbol.SourceType.USER_DEFINED);
    DecompileResults r=d.decompileFunction(f,30,monitor);
    out.println("\n// "+a+" "+f.getName());
    out.println(r.decompileCompleted()?r.getDecompiledFunction().getC():r.getErrorMessage());
   }
  } finally {d.dispose();}
 }
}
