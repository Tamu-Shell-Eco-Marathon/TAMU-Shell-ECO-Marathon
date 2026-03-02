import os
fs_stat = os.statvfs('/')
free_bytes = fs_stat[0] * fs_stat[3] # Block size * Free blocks
print(f"Free space: {free_bytes / 1024} KB")