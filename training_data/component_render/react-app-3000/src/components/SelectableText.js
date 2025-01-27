import React, { useState, useRef, useEffect } from 'react';
import { Heart, Share2, Bookmark, Copy, Check } from 'lucide-react';

const QuoteCard = ({ text, className = '', style = {} }) => {
  const [isLiked, setIsLiked] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [characterPositions, setCharacterPositions] = useState([]);
  const textRef = useRef(null);

  // 默认引用文本
  const defaultQuote = `
**Sonnet 18: Shall I compare thee to a summer's day?**

Shall I compare thee to a summer's day?  
Thou art more lovely and more temperate:  
Rough winds do shake the darling buds of May,  
And summer's lease hath all too short a date:  

Sometime too hot the eye of heaven shines,  
And often is his gold complexion dimm'd;  
And every fair from fair sometime declines,  
By chance or nature's changing course untrimm'd;  

But thy eternal summer shall not fade  
Nor lose possession of that fair thou owest;  
Nor shall Death brag thou wanderest in his shade,  
When in eternal lines to time thou growest;  

So long as men can breathe or eyes can see,  
So long lives this, and this gives life to thee.
`;

  const quoteText = text || defaultQuote;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(quoteText);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };

  // 获取字符位置的函数
  const getCharacterPositions = () => {
    if (textRef.current) {
      const spans = textRef.current.querySelectorAll('span');
      const positions = Array.from(spans).map(span => {
        const rect = span.getBoundingClientRect();
        return {
          character: span.textContent,
          left: rect.left,
          top: rect.top,
          width: rect.width,
          height: rect.height
        };
      });
      setCharacterPositions(positions);
    }
  };

  // 当组件挂载和文本改变时计算位置
  useEffect(() => {
    getCharacterPositions();
    // 在窗口大小调整时重新计算
    window.addEventListener('resize', getCharacterPositions);
    return () => {
      window.removeEventListener('resize', getCharacterPositions);
    };
  }, [quoteText]);

  // 为每个字符渲染单独的span
  const renderTextWithSpans = () => {
    return Array.from(quoteText).map((char, index) => (
      <span 
        key={index} 
        style={{ 
          display: 'inline-block', 
          margin: '0 1px' 
        }}
      >
        {char}
      </span>
    ));
  };

  return (
    <div className="max-w-2xl mx-auto p-6">
      <div 
        className={`relative rounded-xl bg-gradient-to-br from-violet-100 to-pink-100 p-8 shadow-lg ${className}`}
        style={{
          userSelect: 'text',
          cursor: 'text',
          ...style
        }}
      >
        <div className="flex flex-col gap-4">
          <div 
            ref={textRef}
            className="text-xl font-serif italic text-gray-800"
          >
            {renderTextWithSpans()}
          </div>

          {/* 功能按钮 */}
          <div className="flex justify-between items-center mt-4">
            <div className="flex space-x-4">
              <button 
                onClick={() => setIsLiked(!isLiked)}
                className="hover:bg-pink-200 p-2 rounded-full transition-colors"
              >
                {isLiked ? (
                  <Heart fill="red" color="red" className="w-6 h-6" />
                ) : (
                  <Heart className="w-6 h-6 text-gray-600" />
                )}
              </button>
              <button 
                onClick={() => setIsSaved(!isSaved)}
                className="hover:bg-blue-200 p-2 rounded-full transition-colors"
              >
                {isSaved ? (
                  <Bookmark fill="blue" color="blue" className="w-6 h-6" />
                ) : (
                  <Bookmark className="w-6 h-6 text-gray-600" />
                )}
              </button>
              <button 
                onClick={handleCopy}
                className="hover:bg-green-200 p-2 rounded-full transition-colors"
              >
                {isCopied ? (
                  <Check className="w-6 h-6 text-green-600" />
                ) : (
                  <Copy className="w-6 h-6 text-gray-600" />
                )}
              </button>
            </div>
            <button className="hover:bg-gray-200 p-2 rounded-full transition-colors">
              <Share2 className="w-6 h-6 text-gray-600" />
            </button>
          </div>
        </div>
      </div>

      {/* 调试：字符位置 */}
      {/* {characterPositions.length > 0 && (
        <div className="mt-4 text-sm text-gray-600">
          <h3>字符位置:</h3>
          <pre>{JSON.stringify(characterPositions.slice(0, 5), null, 2)}...</pre>
          <p>总字符数: {characterPositions.length}</p>
        </div>
      )} */}
    </div>
  );
};

export default QuoteCard;