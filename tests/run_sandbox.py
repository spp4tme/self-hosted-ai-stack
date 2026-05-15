from sandbox.executor import SandboxExecutor
ex = SandboxExecutor()
r = ex.execute("print(2**10)")
print("stdout:", r.stdout.strip())
print("success:", r.success)
print("duration:", r.duration_s, "s")
print("SANDBOX OK")
