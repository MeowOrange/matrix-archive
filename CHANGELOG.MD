# 2022-03-26 tag:1.4
* Added exit code, log file output
* Handles room ids containing '/'

# 2022-03-12 tag:1.3
* Optimized download mekanism to prevent script from stuck during downloading

# 2022-02-18 tag:1.2
* Added argument ```--no-progress-bar``` to disable beautiful progress bar
  
  Useful when using Portainer to see logs where every time my progress bar refresh, more logs came out

# 2022-02-18 tag:1.1
* Optimized database interaction
* Added progress bar for every operation except for importing keys
* messages.json will not be deleted on second run
* Added code to update ```BadEvent```s when matrix-nio updates in the future