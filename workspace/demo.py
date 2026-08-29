import time, math
print("Running demo.py on cloud runner...")
for i in range(3):
    print(f"step {i}: sqrt({i*10})={math.sqrt(i*10):.2f}")
    time.sleep(0.5)
print("DONE")