#define _GNU_SOURCE
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
int SDL_ShowSimpleMessageBox(unsigned int flags, const char *title,
                             const char *msg, void *window) {
  if (msg && strstr(msg, "Failed to set vsync")) {
    fprintf(stderr, "Suppressed headless VSync popup: %s\n", msg);
    return 0;
  }
  int (*real_fn)(unsigned int,const char*,const char*,void*) =
    dlsym(RTLD_NEXT, "SDL_ShowSimpleMessageBox");
  return real_fn ? real_fn(flags,title,msg,window) : 0;
}
