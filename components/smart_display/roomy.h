#pragma once
// Memory that takes PSRAM first (2026-10-13). The boards build with CONFIG_SPIRAM_USE_CAPS_ALLOC: a plain malloc, new,
// std::string or std::vector never lands in PSRAM, only what asks for it, so everything else shares the few tens of
// kilobytes inside the chip with Wi-Fi and the network stack, which must stay there (packages/hardware/esp32s3-rgb.yaml).
// On a Guition with a few plugin tiles on kept pages that left 25 KB, and a busy moment of Wi-Fi took the rest: a
// picture's download could not grow a small buffer and the screen aborted, or Wi-Fi itself stalled.
//
// What only the screen's logic reads, never DMA or the network, and what can be larger than a few hundred bytes goes
// here: a plugin tile's options and data (runtime_model.h Extra), the documents the plugin host parses them into, the
// plugin objects (tessera::Tile, tessera::Card), the download task's buffers (picture_fetch.h), and what a plugin keeps
// of its own (tessera::Text, tessera::List). A board without PSRAM, the host tests, the render host and the WASM
// preview take the ordinary heap, as before.
//
// An allocation that finds room in neither aborts, as `new` and std::string do on these boards (they build without
// exceptions): with megabytes of PSRAM free that never happens where it did before.
//
// Pure, free of LVGL and ESPHome: tests/test_roomy.cpp checks it on a PC.
#include <cstddef>
#include <cstdlib>
#include <string>
#include <vector>
#ifdef USE_ESP32
#include <esp_heap_caps.h>
#endif

namespace roomy {

// `bytes` in PSRAM where the board has it, else inside the chip; nullptr only when neither has room.
inline void *allocate(size_t bytes) {
#ifdef USE_ESP32
  void *p = heap_caps_malloc(bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  return p ? p : heap_caps_malloc(bytes, MALLOC_CAP_8BIT);
#else
  return std::malloc(bytes);
#endif
}
inline void *reallocate(void *p, size_t bytes) {
#ifdef USE_ESP32
  void *q = heap_caps_realloc(p, bytes, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT);
  return q ? q : heap_caps_realloc(p, bytes, MALLOC_CAP_8BIT);
#else
  return std::realloc(p, bytes);
#endif
}
inline void release(void *p) {
#ifdef USE_ESP32
  heap_caps_free(p);
#else
  std::free(p);
#endif
}

// A standard allocator over allocate(), for std::basic_string and std::vector. Stateless: every one is equal to every
// other, so containers move and swap their blocks as with std::allocator.
template <class T> struct Allocator {
  using value_type = T;
  using is_always_equal = std::true_type;
  using propagate_on_container_move_assignment = std::true_type;
  Allocator() = default;
  template <class U> Allocator(const Allocator<U> &) {}
  T *allocate(size_t n) {
    void *p = roomy::allocate(n * sizeof(T));
    if (!p) std::abort();
    return static_cast<T *>(p);
  }
  void deallocate(T *p, size_t) { roomy::release(p); }
  template <class U> bool operator==(const Allocator<U> &) const { return true; }
  template <class U> bool operator!=(const Allocator<U> &) const { return false; }
};

using Text = std::basic_string<char, std::char_traits<char>, Allocator<char>>;
template <class T> using List = std::vector<T, Allocator<T>>;

// Text from anything with data() and size() (std::string, a string_view), and back.
template <class S> inline Text text(const S &from) { return Text(from.data(), from.size()); }
template <class S> inline std::string plain(const S &from) { return std::string(from.data(), from.size()); }
// Whether two strings of any allocator hold the same characters.
template <class A, class B> inline bool same(const A &a, const B &b) {
  return a.size() == b.size() && (a.empty() || std::char_traits<char>::compare(a.data(), b.data(), a.size()) == 0);
}

}  // namespace roomy
