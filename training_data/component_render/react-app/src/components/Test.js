import React, { useState, useEffect } from 'react';
import { Star, Heart, Share2, MessageSquare, BookmarkPlus, Film, ThumbsUp, Award } from 'lucide-react';
import { useElementsInfo } from '../Position';

const MovieRating = () => {
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [isLiked, setIsLiked] = useState(false);
  const [isSaved, setIsSaved] = useState(false);
  const [showComments, setShowComments] = useState(false);
  const [comment, setComment] = useState('');
  const [comments, setComments] = useState([]);
  const [elementsInfo, setElementsInfo] = useState(null);
  
  // 获取元素信息的函数
  const getElementsInfo = useElementsInfo();

  // 在组件挂载后获取元素信息
  useEffect(() => {
    // 给DOM一点时间完全渲染
    const timer = setTimeout(() => {
      const info = getElementsInfo();
      if (info) {
        setElementsInfo(info);
        console.log('Elements info:', info); // 用于调试
      }
    }, 100);

    return () => clearTimeout(timer);
  }, []); // 空依赖数组意味着只在挂载时运行

  // 可以添加一个函数来更新元素信息
  const updateElementsInfo = () => {
    const info = getElementsInfo();
    if (info) {
      setElementsInfo(info);
      console.log('Updated elements info:', info);
    }
  };

  // 在状态改变时更新元素信息
  useEffect(() => {
    updateElementsInfo();
  }, [showComments]); // 当评论显示状态改变时更新
  
  
  // 评分系统
  const renderStars = () => {
    return [...Array(5)].map((_, index) => {
      const ratingValue = index + 1;
      return (
        <button
          key={index}
          className={`focus:outline-none transition-colors duration-200 ${
            (hover || rating) >= ratingValue ? 'text-yellow-400' : 'text-gray-300'
          }`}
          onClick={() => setRating(ratingValue)}
          onMouseEnter={() => setHover(ratingValue)}
          onMouseLeave={() => setHover(0)}
        >
          <Star className={`w-8 h-8 ${(hover || rating) >= ratingValue ? 'fill-yellow-400' : ''}`} />
        </button>
      );
    });
  };

  // 添加评论
  const handleCommentSubmit = (e) => {
    e.preventDefault();
    if (comment.trim()) {
      setComments([...comments, { id: Date.now(), text: comment, rating }]);
      setComment('');
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6 bg-white rounded-lg shadow">
      {/* 电影信息区域 */}
      <div className="flex items-center space-x-4">
        <Film className="w-12 h-12" />
        <div>
          <h2 className="text-xl font-bold">Movie Title</h2>
          <div className="flex items-center space-x-2">
            <Award className="w-4 h-4" />
            <span className="text-sm">Director's Cut</span>
          </div>
        </div>
      </div>

      {/* 评分区域 */}
      <div className="space-y-4">
        <div className="flex items-center space-x-2">
          {renderStars()}
          <span className="ml-2 text-lg">{rating}/5</span>
        </div>
        
        {/* 交互按钮组 */}
        <div className="flex space-x-4">
          <button
            onClick={() => setIsLiked(!isLiked)}
            className={`flex items-center space-x-1 p-2 rounded-lg transition-colors ${
              isLiked ? 'text-red-500' : 'text-gray-500'
            }`}
          >
            <Heart className={`w-6 h-6 ${isLiked ? 'fill-red-500' : ''}`} />
            <span>Like</span>
          </button>

          <button
            onClick={() => setIsSaved(!isSaved)}
            className={`flex items-center space-x-1 p-2 rounded-lg transition-colors ${
              isSaved ? 'text-blue-500' : 'text-gray-500'
            }`}
          >
            <BookmarkPlus className={`w-6 h-6 ${isSaved ? 'fill-blue-500' : ''}`} />
            <span>Save</span>
          </button>

          <button className="flex items-center space-x-1 p-2 rounded-lg text-gray-500">
            <Share2 className="w-6 h-6" />
            <span>Share</span>
          </button>
        </div>
      </div>

      {/* 评论区域 */}
      <div className="space-y-4">
        <button
          onClick={() => setShowComments(!showComments)}
          className="flex items-center space-x-2 text-gray-600"
        >
          <MessageSquare className="w-6 h-6" />
          <span>{comments.length} Comments</span>
        </button>

        {showComments && (
          <div className="space-y-4">
            <form onSubmit={handleCommentSubmit} className="space-y-2">
              <textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                className="w-full p-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                placeholder="Add your comment..."
                rows="3"
              />
              <button
                type="submit"
                className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600"
              >
                Post Comment
              </button>
            </form>

            <div className="space-y-4">
              {comments.map((comment) => (
                <div key={comment.id} className="p-4 bg-gray-50 rounded-lg">
                  <div className="flex items-center space-x-2 mb-2">
                    {[...Array(comment.rating)].map((_, i) => (
                      <Star key={i} className="w-4 h-4 fill-yellow-400" />
                    ))}
                  </div>
                  <p>{comment.text}</p>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default MovieRating;