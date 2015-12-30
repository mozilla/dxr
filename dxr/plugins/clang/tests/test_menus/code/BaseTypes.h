#ifndef BASETYPES_H
#define BASETYPES_H

class BaseClass {
public:
  virtual void virtualFunc() { }
  virtual void pVirtualFunc() = 0;
};

struct BaseStruct {
};

#endif
