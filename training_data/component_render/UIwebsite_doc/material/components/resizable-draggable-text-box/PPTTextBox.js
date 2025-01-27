// MAKE SURE TO KEEP IN IN THE STYLE OF POWERPOINT'S Text Box with Resizing Handles
// MAKE SURE TO KEEP IN IN THE STYLE OF POWERPOINT'S Text Box with Resizing Handles
// MAKE SURE TO KEEP IN IN THE STYLE OF POWERPOINT'S Text Box with Resizing Handles

import React, { useState } from 'react';

const PPTTextBox = () => {
  const [position, setPosition] = useState({ x: 100, y: 100 });
  const [size, setSize] = useState({ width: 200, height: 100 });
  const [rotation, setRotation] = useState(0);
  const [text, setText] = useState('双击编辑文本');
  const [isEditing, setIsEditing] = useState(false);

  const resizeHandles = [
    { position: 'top-left', cursor: 'nwse-resize' },
    { position: 'top-center', cursor: 'ns-resize' },
    { position: 'top-right', cursor: 'nesw-resize' },
    { position: 'middle-left', cursor: 'ew-resize' },
    { position: 'middle-right', cursor: 'ew-resize' },
    { position: 'bottom-left', cursor: 'nesw-resize' },
    { position: 'bottom-center', cursor: 'ns-resize' },
    { position: 'bottom-right', cursor: 'nwse-resize' }
  ];

  const handleResize = (e, handle) => {
    e.preventDefault();
    const startX = e.clientX;
    const startY = e.clientY;
    const startWidth = size.width;
    const startHeight = size.height;
    const startLeft = position.x;
    const startTop = position.y;

    const onMouseMove = (moveEvent) => {
      const deltaX = moveEvent.clientX - startX;
      const deltaY = moveEvent.clientY - startY;

      let newWidth = startWidth;
      let newHeight = startHeight;
      let newLeft = startLeft;
      let newTop = startTop;

      switch(handle) {
        case 'top-left':
          newWidth = startWidth - deltaX;
          newHeight = startHeight - deltaY;
          newLeft = startLeft + deltaX;
          newTop = startTop + deltaY;
          break;
        case 'top-center':
          newHeight = startHeight - deltaY;
          newTop = startTop + deltaY;
          break;
        case 'top-right':
          newWidth = startWidth + deltaX;
          newHeight = startHeight - deltaY;
          newTop = startTop + deltaY;
          break;
        case 'middle-left':
          newWidth = startWidth - deltaX;
          newLeft = startLeft + deltaX;
          break;
        case 'middle-right':
          newWidth = startWidth + deltaX;
          break;
        case 'bottom-left':
          newWidth = startWidth - deltaX;
          newHeight = startHeight + deltaY;
          newLeft = startLeft + deltaX;
          break;
        case 'bottom-center':
          newHeight = startHeight + deltaY;
          break;
        case 'bottom-right':
          newWidth = startWidth + deltaX;
          newHeight = startHeight + deltaY;
          break;
      }

      setSize({ 
        width: Math.max(50, newWidth), 
        height: Math.max(30, newHeight) 
      });
      setPosition({ 
        x: newLeft, 
        y: newTop 
      });
    };

    const onMouseUp = () => {
      document.removeEventListener('mousemove', onMouseMove);
      document.removeEventListener('mouseup', onMouseUp);
    };

    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', onMouseUp);
  };

  return (
    <div 
      style={{
        position: 'absolute',
        left: position.x,
        top: position.y,
        width: size.width,
        height: size.height,
        transform: `rotate(${rotation}deg)`,
        border: '2px solid blue',
        position: 'absolute'
      }}
    >
      {isEditing ? (
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          onBlur={() => setIsEditing(false)}
          style={{ 
            width: '100%', 
            height: '100%', 
            resize: 'none', 
            border: 'none', 
            outline: 'none' 
          }}
          autoFocus
        />
      ) : (
        <div 
          onDoubleClick={() => setIsEditing(true)}
          style={{ 
            width: '100%', 
            height: '100%', 
            display: 'flex', 
            alignItems: 'center', 
            justifyContent: 'center' 
          }}
        >
          {text}
        </div>
      )}

      {resizeHandles.map((handle) => (
        <div
          key={handle.position}
          style={{
            position: 'absolute',
            width: '8px',
            height: '8px',
            backgroundColor: 'blue',
            ...(handle.position.includes('top') && { top: '-4px' }),
            ...(handle.position.includes('bottom') && { bottom: '-4px' }),
            ...(handle.position.includes('left') && { left: '-4px' }),
            ...(handle.position.includes('right') && { right: '-4px' }),
            ...(handle.position.includes('center') && { 
              left: '50%', 
              transform: 'translateX(-50%)' 
            }),
            ...(handle.position.includes('middle') && { 
              top: '50%', 
              transform: 'translateY(-50%)' 
            }),
            cursor: handle.cursor
          }}
          onMouseDown={(e) => handleResize(e, handle.position)}
        />
      ))}
    </div>
  );
};

export default PPTTextBox;