import { BrowserRouter, Routes, Route } from 'react-router-dom';
import PipelineDashboard from './components/PipelineDashboard';
import './App.css';

function App() {
  return (
    <BrowserRouter>
      <div className="App">
        <Routes>
          <Route path="/" element={<PipelineDashboard />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

export default App
