
import React from 'react';
import './App.css';
import GridTable from './components/GridTable';

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
        <GridTable />
      </div>
    </div>
  );
}

export default App;
