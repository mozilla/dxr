#include <stdint.h>
#include <string.h>
#include <assert.h>
#include <limits.h>

/** Representation of a BitField, well really, just some annoying part of it */
class BitField {
private:
	/** Definition of underlying type for the bitfield*/
	typedef unsigned int _word;

	/** Number of bits per word */
	static const size_t _bitsPerWord = CHAR_BIT * sizeof(_word);

	/** Number of words for size */
	size_t _words() const{
		return (_size + _bitsPerWord - 1) / _bitsPerWord;
	}

	/** Underlying word array */
	_word* _bits;
	size_t _size;
public:
	/** Create a new empty bitfield */
	BitField(size_t size){
		_size = size;
		_bits = new _word[_words()];
	}

	/** Copy create a bitfield from another */
	BitField(const BitField& bf){
		_size = bf._size;
		_bits = new _word[_words()];
		for(size_t i = 0; i < _words(); i++)
			_bits[i] = bf._bits[i];
	}

	/** Destructor */
	~BitField(){
		if(_bits){
			delete[] _bits;
			_bits = NULL;
		}
	}

	BitField& operator= (const BitField& rhs){
		for(size_t i = 0; i < _words(); i++)
			_bits[i] = rhs._bits[i];
		return *this;
	}

	BitField& operator&= (const BitField& rhs){
		for(size_t i = 0; i < _words(); i++)
			_bits[i] &= rhs._bits[i];
		return *this;
	}
};

inline BitField operator&(const BitField& lhs, const BitField& rhs){
	BitField retval(lhs);
	retval &= rhs;
	return retval;
}


