// clang++ -std=c++17 -Wall -Wextra -Werror -I. tests/test_roomy.cpp -o /tmp/test_roomy && /tmp/test_roomy
// Memory that takes PSRAM first (roomy.h): its allocator in a string and a list, which move and swap as std's do, and
// the helpers between a roomy::Text and a std::string. On a PC it is the ordinary heap; the board's PSRAM path is the same
// code with heap_caps_malloc.
#include "../components/smart_display/roomy.h"
#include <cassert>
#include <cstdio>
#include <string>
#include <utility>

int main() {
  // A text grows, copies, moves and compares as a std::string does.
  roomy::Text a = "Night Shift";
  a += " at the Lighthouse";
  assert(a.size() == 29 && a == "Night Shift at the Lighthouse");
  roomy::Text b = a;
  assert(b == a && b.data() != a.data());
  const char *block = b.data();
  roomy::Text c = std::move(b);
  assert(c.data() == block);   // a move keeps the block: every allocator is equal to every other
  std::swap(a, c);
  assert(a == c);
  // Long enough to leave the string's own small buffer: the allocator's block.
  roomy::Text big(4096, 'x');
  big.append(4096, 'y');
  assert(big.size() == 8192 && big[0] == 'x' && big[8191] == 'y');
  // To and from a std::string, and compared with one.
  const std::string plain = roomy::plain(a);
  assert(plain == "Night Shift at the Lighthouse");
  assert(roomy::same(a, plain) && roomy::same(plain, a) && !roomy::same(a, std::string("Night")));
  assert(roomy::same(roomy::Text(), std::string()));
  assert(roomy::text(plain) == a);
  // A list of anything, with room reserved, grown and moved.
  struct Film { char title[52]; float rating; };
  roomy::List<Film> films;
  films.reserve(2);
  for (int i = 0; i < 40; ++i) films.push_back({{'A', char('a' + i % 26), 0}, 5.0f + i * 0.1f});
  assert(films.size() == 40 && films[39].title[0] == 'A' && films[39].rating > 8.8f);
  roomy::List<Film> kept = std::move(films);
  assert(kept.size() == 40 && films.empty());
  // The raw calls the JSON documents use: grow keeps the bytes.
  char *raw = static_cast<char *>(roomy::allocate(16));
  assert(raw);
  for (int i = 0; i < 16; ++i) raw[i] = char(i);
  raw = static_cast<char *>(roomy::reallocate(raw, 4096));
  assert(raw && raw[15] == 15);
  roomy::release(raw);
  std::puts("test_roomy: ok");
  return 0;
}
