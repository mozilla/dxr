class Ptr
{
  public:
    Ptr(Ptr* aPtr)
      : mPtr(aPtr)
    {
    }

    operator Ptr*() const
    {
      return mPtr;
    }

    Ptr& operator= (const Ptr&)
    {
      return *mPtr;
    }

    private:
      Ptr* mPtr;
};


class nsAuth
{

};


int main(int argc, char* argv[]) {
  return 0;
}


#define SOMETHING
