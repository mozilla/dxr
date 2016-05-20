//// Qualnames involving template instantiation and specialization:
template<class T>
void fud(T ) {}
// Full specialization:
template<>
inline void fud(int ) {}

template<typename T>
class Baz {};

template<typename T>
void guz(Baz<T> ) {}

struct Gub {
  template<typename T>
  void bug(T ) {}
};
// Full specialization:
template<> inline void Gub::bug(char ) {}

template<typename T>
struct Gleb {
  template<typename U>
  void lerb(U ) {}
};
// Full specialization (seems like you can't partially specialize a templated
// method of a templated class):
template<>
template<>
inline void Gleb<char>::lerb(int ) {}

template<typename T>
struct Derb {
  void flarb(T ) {}
};
// Partial specialization:
template<typename T>
struct Derb<T*> {
  void flarb(T * ) {}
};
