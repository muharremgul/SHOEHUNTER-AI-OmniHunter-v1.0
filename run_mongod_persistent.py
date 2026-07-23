import subprocess
import time
import sys

print("Starting background mongod daemon...")
proc = subprocess.Popen([
    r"C:\Program Files\MongoDB\Server\8.3\bin\mongod.exe",
    "--dbpath", r"C:\Users\ÖGR1\Documents\Ayakkabi\data\mongodb_db",
    "--port", "27017"
])
print("Mongod running PID:", proc.pid)
sys.stdout.flush()

while True:
    time.sleep(60)
