import React, { useState } from 'react';

const StarRating = () => {
  const [rating, setRating] = useState(4);
  const [hover, setHover] = useState(null);

  return (
    <div style={{ display: 'flex', alignItems: 'center' }}>
      {[...Array(5)].map((star, index) => {
        index += 1;
        return (
          <button
            type="button"
            key={index}
            className={index <= (hover || rating) ? "on" : "off"}
            onClick={() => setRating(index)}
            onMouseEnter={() => setHover(index)}
            onMouseLeave={() => setHover(rating)}
            style={{ border: 'none', background: 'none', cursor: 'pointer', fontSize: '24px' }}
          >
            <span style={{ color: index <= (hover || rating) ? "#FFD700" : "#808080" }}>&#9733;</span>
          </button>
        );
      })}
    </div>
  );
};

export default StarRating;