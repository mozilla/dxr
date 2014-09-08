describe ('Chai testing', function(){
  describe('readability functions', function(){
    it('should be a string and equal to hello world', function(){
      var word = "hello world";
      word.should.be.a("string");
      word.should.equal("hello world");
    });
  });
});