// @category Pace
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.listing.*;
import java.io.PrintWriter;
import java.util.regex.*;
// Read-only: decompile every function and report those whose C mentions an
// MMIO address matching the given regex (e.g. "b000[28][0-9a-f]{3}").
// Args: <out.txt> <regex>
public class FindMmioUsers extends GhidraScript {
 public void run() throws Exception {
  String[] args=getScriptArgs();
  Pattern p=Pattern.compile("(?i)"+args[1]);
  DecompInterface d=new DecompInterface();d.openProgram(currentProgram);
  int n=0,hits=0;
  try(PrintWriter out=new PrintWriter(args[0])){
   for(Function f:currentProgram.getFunctionManager().getFunctions(true)){
    n++;
    DecompileResults r=d.decompileFunction(f,30,monitor);
    if(!r.decompileCompleted())continue;
    String c=r.getDecompiledFunction().getC();
    Matcher m=p.matcher(c);
    if(!m.find())continue;
    hits++;
    out.println("\n// ==== "+f.getEntryPoint()+" "+f.getName());
    for(String line:c.split("\n"))if(p.matcher(line).find())out.println("//   "+line.trim());
   }
   out.println("\n// scanned "+n+" functions, "+hits+" hits");
  } finally {d.dispose();}
 }
}
