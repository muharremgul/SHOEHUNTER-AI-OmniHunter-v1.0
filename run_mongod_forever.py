import subprocess

cmd = [
    r"C:\Program Files\MongoDB\Server\8.3\bin\mongod.exe",
    "--dbpath", r"C:\Users\ÖGR1\Documents\Ayakkabi\data\mongodb_db",
    "--port", "27017"
]

proc = subprocess.Popen(cmd)
print("Started mongod process PID:", proc.pid)
import time
time.sleep(10)
