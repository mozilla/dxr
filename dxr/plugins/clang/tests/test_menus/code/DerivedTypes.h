#ifndef DERIVEDTYPES_H
#define DERIVEDTYPES_H

#include "BaseTypes.h"

class DerivedClass : public BaseClass {
public:
  void virtualFunc();
  void pVirtualFunc() { }
};

struct DerivedStruct : public BaseStruct {
};

#endif
