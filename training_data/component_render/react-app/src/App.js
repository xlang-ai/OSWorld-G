
import React from 'react';
import './App.css';
import '@fontsource/roboto/300.css';
import '@fontsource/roboto/400.css';
import '@fontsource/roboto/500.css';
import '@fontsource/roboto/700.css';

function App() {
  return (
    <div className="App">
      <div className="container" style={{
        maxWidth: '800px',
        margin: '20px auto',
        padding: '24px',
        backgroundColor: '#ffffff',
        borderRadius: '8px',
        overflow: 'visible', // 确保内容不会被裁剪
        }}>
        <h1>Hello, World</h1>
      </div>
    </div>
  );
}

export default App;
