from amitools.vamos.AmigaLibrary import *
from lexec.ExecStruct import *
from amitools.vamos.Log import log_exec
from amitools.vamos.Exceptions import *
from amitools.vamos.AccessStruct import AccessStruct

class ExecLibrary(AmigaLibrary):
  name = "exec.library"

  def __init__(self, lib_mgr, alloc, version=39, profile=False):
    AmigaLibrary.__init__(self, self.name, version, ExecLibraryDef, profile)
    log_exec.info("open exec.library V%d", self.version)
    self.lib_mgr = lib_mgr
    self.alloc = alloc
    
  def setup_lib(self, lib, ctx):
    AmigaLibrary.setup_lib(self, lib, ctx)
    # setup exec memory
    lib.access.w_s("LibNode.lib_Version", self.version)

  def set_this_task(self, lib, process):
    lib.access.w_s("ThisTask",process.this_task.addr)
    self.stk_lower = process.stack_base
    self.stk_upper = process.stack_end
    
  # ----- System -----
  
  def Disable(self, lib, ctx):
    log_exec.info("Disable")
  def Enable(self, lib, ctx):
    log_exec.info("Enable")
  def Forbid(self, lib, ctx):
    log_exec.info("Forbid")
  def Permit(self, lib, ctx):
    log_exec.info("Permit")
    
  def FindTask(self, lib, ctx):
    task_ptr = ctx.cpu.r_reg(REG_A1)
    if task_ptr == 0:
      addr = lib.access.r_s("ThisTask")
      log_exec.info("FindTask: me=%06x" % addr)
      return addr
    else:
      task_name = ctx.mem.access.r_cstr(task_ptr)
      log_exec.info("Find Task: %s" % task_name)
      raise UnsupportedFeatureError("FindTask: other task!");
  
  def SetSignals(self, lib, ctx):
    new_signals = ctx.cpu.r_reg(REG_D0)
    signal_mask = ctx.cpu.r_reg(REG_D1)
    old_signals = 0
    log_exec.info("SetSignals: new_signals=%08x signal_mask=%08x old_signals=%08x" % (new_signals, signal_mask, old_signals))
    return old_signals
  
  def StackSwap(self, lib, ctx):
    stsw_ptr = ctx.cpu.r_reg(REG_A0)
    stsw = AccessStruct(ctx.mem,StackSwapDef,struct_addr=stsw_ptr)
    # get new stack values
    new_lower = stsw.r_s('stk_Lower')
    new_upper = stsw.r_s('stk_Upper')
    new_pointer = stsw.r_s('stk_Pointer')
    # retrieve current (old) stack
    old_lower = self.stk_lower
    old_upper = self.stk_upper
    old_pointer = ctx.cpu.r_reg(REG_A7) # addr of sys call return
    # get adress of callee
    callee = ctx.mem.access.r32(old_pointer)
    # we report the old stack befor callee
    old_pointer += 4
    log_exec.info("StackSwap: old(lower=%06x,upper=%06x,ptr=%06x) new(lower=%06x,upper=%06x,ptr=%06x)" % (old_lower,old_upper,old_pointer,new_lower,new_upper,new_pointer))
    stsw.w_s('stk_Lower', old_lower)
    stsw.w_s('stk_Upper', old_upper)
    stsw.w_s('stk_Pointer', old_pointer)
    self.stk_lower = new_lower
    self.stk_upper = new_upper
    # put callee's address on new stack
    new_pointer -= 4
    ctx.mem.access.w32(new_pointer,callee)
    # activate new stack
    ctx.cpu.w_reg(REG_A7, new_pointer)
    
  # ----- Libraries -----
  
  def OpenLibrary(self, lib, ctx):
    ver = ctx.cpu.r_reg(REG_D0)
    name_ptr = ctx.cpu.r_reg(REG_A1)
    name = ctx.mem.access.r_cstr(name_ptr)
    lib = self.lib_mgr.open_lib(name, ver, ctx)
    log_exec.info("OpenLibrary: '%s' V%d -> %s" % (name, ver, lib))
    if lib == None:
      return 0
    else:
      return lib.lib_base
  
  def OldOpenLibrary(self, lib, ctx):
    name_ptr = ctx.cpu.r_reg(REG_A1)
    name = ctx.mem.access.r_cstr(name_ptr)
    lib = self.lib_mgr.open_lib(name, 0, ctx)
    log_exec.info("OldOpenLibrary: '%s' -> %s" % (name, lib))
    return lib.lib_base
  
  def CloseLibrary(self, lib, ctx):
    lib_addr = ctx.cpu.r_reg(REG_A1)
    lib = self.lib_mgr.close_lib(lib_addr,ctx)
    if lib != None:
      log_exec.info("CloseLibrary: '%s' -> %06x" % (lib, lib.lib_base))
    else:
      raise VamosInternalError("CloseLibrary: Unknown library to close: ptr=%06x" % lib_addr)
  
  # ----- Memory Handling -----
  
  def AllocMem(self, lib, ctx):
    size = ctx.cpu.r_reg(REG_D0)
    flags = ctx.cpu.r_reg(REG_D1)
    # label alloc
    pc = self.get_callee_pc(ctx)
    tag = ctx.label_mgr.get_mem_str(pc)
    name = "AllocMem(%06x = %s)" % (pc,tag)
    mb = self.alloc.alloc_memory(name,size)
    log_exec.info("AllocMem: %s" % mb)
    return mb.addr
  
  def FreeMem(self, lib, ctx):
    size = ctx.cpu.r_reg(REG_D0)
    addr = ctx.cpu.r_reg(REG_A1)
    if addr == 0 or size == 0:
      log_exec.info("FreeMem: freeing NULL")
      return
    mb = self.alloc.get_memory(addr)
    if mb != None:
      log_exec.info("FreeMem: %s" % mb)
      self.alloc.free_memory(mb)
    else:
      raise VamosInternalError("FreeMem: Unknown memory to free: ptr=%06x size=%06x" % (addr, size))

  def AllocVec(self, lib, ctx):
    size = ctx.cpu.r_reg(REG_D0)
    flags = ctx.cpu.r_reg(REG_D1)
    mb = self.alloc.alloc_memory("AllocVec(@%06x)" % self.get_callee_pc(ctx),size)
    log_exec.info("AllocVec: %s" % mb)
    return mb.addr
    
  def FreeVec(self, lib, ctx):
    addr = ctx.cpu.r_reg(REG_A1)
    if addr == 0:
      log_exec.info("FreeVec: freeing NULL")
      return
    mb = self.alloc.get_memory(addr)
    if mb != None:
      log_exec.info("FreeVec: %s" % mb)
      self.alloc.free_memory(mb)
    else:
      raise VamosInternalError("FreeVec: Unknown memory to free: ptr=%06x" % (addr))
  
  # ----- Misc -----
  
  def RawDoFmt(self, lib, ctx):
    format_ptr = ctx.cpu.r_reg(REG_A0)
    format     = ctx.mem.access.r_cstr(format_ptr)
    data_ptr   = ctx.cpu.r_reg(REG_A1)
    putch_ptr  = ctx.cpu.r_reg(REG_A2)
    pdata_ptr  = ctx.cpu.r_reg(REG_A3)
    log_exec.info("RawDoFmt: format='%s' data=%06x putch=%06x pdata=%06x" % (format, data_ptr, putch_ptr, pdata_ptr))
  
  # ----- Message Passing -----
  
  def PutMsg(self, lib, ctx):
    port_addr = ctx.cpu.r_reg(REG_A0)
    msg_addr = ctx.cpu.r_reg(REG_A1)
    log_exec.info("PutMsg: port=%06x msg=%06x" % (port_addr, msg_addr))
    has_port = ctx.port_mgr.has_port(port_addr)
    if not has_port:
      raise VamosInternalError("PutMsg: on invalid Port (%06x) called!" % port_addr)
    ctx.port_mgr.put_msg(port_addr, msg_addr)
      
  def GetMsg(self, lib, ctx):
    port_addr = ctx.cpu.r_reg(REG_A0)
    log_exec.info("GetMsg: port=%06x" % (port_addr))
    has_port = ctx.port_mgr.has_port(port_addr)
    if not has_port:
      raise VamosInternalError("GetMsg: on invalid Port (%06x) called!" % port_addr)
    msg_addr = ctx.port_mgr.get_msg(port_addr)
    if msg_addr != None:
      log_exec.info("GetMsg: got message %06x" % (msg_addr))
      return msg_addr
    else:
      log_exec.info("GetMsg: no message available!")
      return 0
  
  def WaitPort(self, lib, ctx):
    port_addr = ctx.cpu.r_reg(REG_A0)
    log_exec.info("WaitPort: port=%06x" % (port_addr))
    has_port = ctx.port_mgr.has_port(port_addr)
    if not has_port:
      raise VamosInternalError("WaitPort: on invalid Port (%06x) called!" % port_addr)
    has_msg = ctx.port_mgr.has_msg(port_addr)
    if not has_msg:
      raise UnsupportedFeatureError("WaitPort on empty message queue called: Port (%06x)" % port_addr)
    msg_addr = ctx.port_mgr.get_msg(port_addr)
    log_exec.info("WaitPort: got message %06x" % (msg_addr))
    return msg_addr
