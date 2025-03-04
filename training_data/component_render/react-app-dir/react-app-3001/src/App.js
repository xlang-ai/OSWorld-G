
import React from 'react';
import './App.css';
import ProgressAlert from './components/ProgressAlert';
import RandomContainer from './components/RandomContainer';

function App() {
  return (
    <div className="App">
      <RandomContainer>
        <ProgressAlert />
      </RandomContainer>
    </div>
  );
}

export default App;
