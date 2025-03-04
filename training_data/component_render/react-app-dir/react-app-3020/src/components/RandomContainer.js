import React, { useState, useEffect } from 'react';

const RandomContainer = ({ children }) => {
  const [dimensions, setDimensions] = useState({
    width: 800,
    height: 600,
    left: 0,
    top: 0
  });

  useEffect(() => {
    // Generate random dimensions within reasonable bounds
    const minWidth = 400;
    const maxWidth = 1920;
    const minHeight = 300;
    const maxHeight = 1080;
    const screenWidth = 1920;
    const screenHeight = 1080;

    const randomWidth = Math.floor(Math.random() * (maxWidth - minWidth + 1)) + minWidth;
    const randomHeight = Math.floor(Math.random() * (maxHeight - minHeight + 1)) + minHeight;

    // Calculate maximum possible position while keeping container within screen
    const maxLeft = screenWidth - randomWidth;
    const maxTop = screenHeight - randomHeight;

    // Generate random position
    const randomLeft = Math.floor(Math.random() * maxLeft);
    const randomTop = Math.floor(Math.random() * maxTop);

    setDimensions({
      width: randomWidth,
      height: randomHeight,
      left: randomLeft,
      top: randomTop
    });
  }, []); // Only run once on mount

  return (
    <div className="container">
        <div 
        className="fixed bg-white p-6 overflow-auto"
        style={{
            width: `${dimensions.width}px`,
            height: `${dimensions.height}px`,
            left: `${dimensions.left}px`,
            top: `${dimensions.top}px`
        }}
        >
            {children}
        </div>
    </div>
  );
};

export default RandomContainer;