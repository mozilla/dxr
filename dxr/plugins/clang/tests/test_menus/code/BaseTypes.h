#ifndef BASETYPES_H
#define BASETYPES_H

class BaseClass {
public:
  virtual ~BaseClass() {}
  virtual void virtualFunc() { }
  virtual void pVirtualFunc() = 0;
};

struct BaseStruct {
};

// I'm giving this class a single-letter name so that when we test for
// destructor extents it'll be easy to tell if we skipped over the '~'
// incorrectly.
class Z {
public:
  ~Z();
};

#endif
