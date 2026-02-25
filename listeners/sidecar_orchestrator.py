# -*- coding: utf-8 -*-
"""listeners/sidecar_orchestrator.po - sidecar orchestrator for background services.

A consolidated version that includes all services from the provided files."""
from __future__ import annotations
import argparse, os, subprocess, sys, time
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# This function is imported from another module, let's assume it exists.
# In real code you need to make sure it is available.
def _load_p2p_settings_mock():
    """Mock function for _load_p2p."""
    return {"enable": os.getenv("P2P_ENABLE_MOCK", "0")}

_load_p2p = _load_p2p_settings_mock

def _spawn(mod: str, *args):
    """Starts the child process Pothon."""
    argv = [sys.executable, "-m", mod, *args]
    return subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def _flag(name: str) -> bool:
    """Checks the value of an environment variable as a boolean flag."""
    try:
        return bool(int(os.getenv(name, "0")))
    except (ValueError, TypeError):
        return False

def _p2p_enabled() -> bool:
    """Checks whether P2P transport is enabled."""
    s = _load_p2p()
    if bool(int(os.getenv("P2P_ENABLE", "0"))):
        return True
    return bool(s.get("enable"))

def main(argv=None) -> int:
    """The main function of the orchestrator."""
    ap = argparse.ArgumentParser(description="Ester sidecar orchestrator")
    ap.add_argument("--poll", type=int, default=10, help="Interval oprosa v sekundakh")
    args = ap.parse_args(argv)

    # --- Initial start of services ---

    # Bezuslovnye i osnovnye sluzhby
    usb = _spawn("listeners.usb_dyn_driver")
    p2p: Optional[subprocess.Popen] = _spawn("listeners.p2p_spooler", "--loop") if _p2p_enabled() else None

    # Services controlled by environment variables from all files
    ps = _spawn("listeners.portable_sync", "--loop") if _flag("PORTABLE_SYNC_ENABLE") else None
    lc = _spawn("listeners.lan_catalog", "--loop") if _flag("LAN_CATALOG_ENABLE") else None # sidecar_orchestrator.py26 (lan_catalog_service)
    lj = _spawn("listeners.lan_jobs_runner", "--loop") if _flag("LAN_JOBS_ENABLE") else None
    ur = _spawn("listeners.usb_recovery_autorun", "--loop") if _flag("USB_RECOVERY_ENABLE") or _flag("USB_AUTORUN_ENABLE") else None
    lms = _spawn("listeners.lmstudio_autodetect", "--loop") if _flag("LMSTUDIO_ENABLE") else None
    prj = _spawn("listeners.projects_inbox", "--loop") if _flag("PROJECTS_INBOX_ENABLE") else None
    pkg = _spawn("listeners.usb_pkg_scanner", "--loop") if _flag("PKG_IMPORTER_ENABLE") else None
    scs = _spawn("listeners.selfcare_scheduler", "--loop") if _flag("SELFCARE_ENABLE") else None
    tg = _spawn("listeners.telegram_bot", "--loop") if _flag("TELEGRAM_ENABLE") else None
    la = _spawn("listeners.llm_autoconfig", "--loop") if _flag("LLM_AUTOCONFIG_ENABLE") else None
    ud = _spawn("listeners.usb_deploy_watcher", "--loop") if _flag("USB_DEPLOY_ENABLE") else None
    zc = _spawn("listeners.usb_zc_deploy", "--loop") if _flag("USB_ZC_DEPLOY_ENABLE") else None
    reg = _spawn("listeners.node_registry_agent", "--loop") if _flag("REGISTRY_ENABLE") else None # sidecar_orchestrator.py21, sidecar_orchestrator.py20
    usb_hotask = _spawn("listeners.usb_hotask", "--loop") if _flag("USB_HOTASK_ENABLE") else None # sidecar_orchestrator.py22
    hyb = _spawn("listeners.hybrid_job_router", "--loop") if _flag("HYBRID_QUEUE_ENABLE") else None # sidecar_orchestrator.py19
    udp = _spawn("listeners.lan_reply_listener", "--loop") if _flag("LAN_REPLY_UDP_ENABLE") else None # sidecar_orchestrator.py24
    autolink = _spawn("listeners.auto_link_favorites", "--loop") if _flag("AUTOLINK_ENABLE") else None # sidecar_orchestrator.py23
    usbw = _spawn("listeners.usb_bootstrap_watcher", "--loop") if _flag("USB_BOOTSTRAP_ENABLE") else None # sidecar_orchestrator.py25

    # Display startup status
    print(f"[sidecar] usb_dyn_driver=on", flush=True)
    print(f"[sidecar] p2p_spooler={'on' if p2p else 'off'}", flush=True)
    print(f"[sidecar] portable_sync={'on' if ps else 'off'}", flush=True)
    print(f"[sidecar] lan_catalog={'on' if lc else 'off'}", flush=True)
    print(f"[sidecar] lan_jobs_runner={'on' if lj else 'off'}", flush=True)
    print(f"[sidecar] usb_recovery_autorun={'on' if ur else 'off'}", flush=True)
    print(f"[sidecar] lmstudio_autodetect={'on' if lms else 'off'}", flush=True)
    print(f"[sidecar] projects_inbox={'on' if prj else 'off'}", flush=True)
    print(f"[sidecar] usb_pkg_scanner={'on' if pkg else 'off'}", flush=True)
    print(f"[sidecar] selfcare_scheduler={'on' if scs else 'off'}", flush=True)
    print(f"[sidecar] telegram_bot={'on' if tg else 'off'}", flush=True)
    print(f"[sidecar] llm_autoconfig={'on' if la else 'off'}", flush=True)
    print(f"[sidecar] usb_deploy_watcher={'on' if ud else 'off'}", flush=True)
    print(f"[sidecar] usb_zc_deploy={'on' if zc else 'off'}", flush=True)
    print(f"[sidecar] node_registry_agent={'on' if reg else 'off'}", flush=True)
    print(f"[sidecar] usb_hotask={'on' if usb_hotask else 'off'}", flush=True)
    print(f"[sidecar] hybrid_job_router={'on' if hyb else 'off'}", flush=True)
    print(f"[sidecar] lan_reply_listener={'on' if udp else 'off'}", flush=True)
    print(f"[sidecar] auto_link_favorites={'on' if autolink else 'off'}", flush=True)
    print(f"[sidecar] usb_bootstrap_watcher={'on' if usbw else 'off'}", flush=True)

    try:
        while True:
            time.sleep(max(2, int(args.poll)))

            def _dyn(flag, proc, mod):
                """Restart a process if it crashes, or start/stop by flag."""
                # Run if the flag is set but there is no process
                if flag() and not proc:
                    return _spawn(mod, "--loop")
                
                # Stop if the flag is cleared but the process is running
                if not flag() and proc:
                    try:
                        proc.terminate()
                        proc.wait(timeout=3)
                    except Exception:
                        try:
                            proc.kill()
                        except Exception:
                            pass
                    return None
                
                # Restart if the process has terminated and the flag is still set
                if proc and proc.poll() is not None and flag():
                    return _spawn(mod, "--loop")
                
                return proc

            # Checking and updating the status of each service
            if usb and usb.poll() is not None:
                usb = _spawn("listeners.usb_dyn_driver")
            
            p2p = _dyn(_p2p_enabled, p2p, "listeners.p2p_spooler")
            ps  = _dyn(lambda:_flag("PORTABLE_SYNC_ENABLE"), ps, "listeners.portable_sync")
            lc  = _dyn(lambda:_flag("LAN_CATALOG_ENABLE"), lc, "listeners.lan_catalog")
            lj  = _dyn(lambda:_flag("LAN_JOBS_ENABLE"), lj, "listeners.lan_jobs_runner")
            ur  = _dyn(lambda: (_flag("USB_RECOVERY_ENABLE") or _flag("USB_AUTORUN_ENABLE")), ur, "listeners.usb_recovery_autorun")
            lms = _dyn(lambda:_flag("LMSTUDIO_ENABLE"), lms, "listeners.lmstudio_autodetect")
            prj = _dyn(lambda:_flag("PROJECTS_INBOX_ENABLE"), prj, "listeners.projects_inbox")
            pkg = _dyn(lambda:_flag("PKG_IMPORTER_ENABLE"), pkg, "listeners.usb_pkg_scanner")
            scs = _dyn(lambda:_flag("SELFCARE_ENABLE"), scs, "listeners.selfcare_scheduler")
            tg  = _dyn(lambda:_flag("TELEGRAM_ENABLE"), tg, "listeners.telegram_bot")
            la  = _dyn(lambda:_flag("LLM_AUTOCONFIG_ENABLE"), la, "listeners.llm_autoconfig")
            ud  = _dyn(lambda:_flag("USB_DEPLOY_ENABLE"), ud, "listeners.usb_deploy_watcher")
            zc  = _dyn(lambda:_flag("USB_ZC_DEPLOY_ENABLE"), zc, "listeners.usb_zc_deploy")
            reg = _dyn(lambda:_flag("REGISTRY_ENABLE"), reg, "listeners.node_registry_agent")
            usb_hotask = _dyn(lambda:_flag("USB_HOTASK_ENABLE"), usb_hotask, "listeners.usb_hotask")
            hyb = _dyn(lambda:_flag("HYBRID_QUEUE_ENABLE"), hyb, "listeners.hybrid_job_router")
            udp = _dyn(lambda:_flag("LAN_REPLY_UDP_ENABLE"), udp, "listeners.lan_reply_listener")
            autolink = _dyn(lambda:_flag("AUTOLINK_ENABLE"), autolink, "listeners.auto_link_favorites")
            usbw = _dyn(lambda:_flag("USB_BOOTSTRAP_ENABLE"), usbw, "listeners.usb_bootstrap_watcher")

    except KeyboardInterrupt:
        pass
    finally:
        # Correct termination of all child processes
        all_processes = (
            usb, p2p, ps, lc, lj, ur, lms, prj, pkg, scs, tg, la, ud, zc, 
            reg, usb_hotask, hyb, udp, autolink, usbw
        )
        for p in all_processes:
            if p and p.poll() is None:
                try:
                    p.terminate()
                    p.wait(timeout=3)
                except Exception:
                    try:
                        p.kill()
                    except Exception:
                        pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())