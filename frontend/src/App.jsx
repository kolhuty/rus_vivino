
import { Routes, Route } from 'react-router-dom';

import Camera from './components/Camera.jsx'
import Sommelier from './components/Sommelier.jsx'
import './styles/App.css'


function App() {
  return (
    <Routes> 
      <Route path="/" element={<Camera />} />
      <Route path="/sommelier" element={<Sommelier />} />
    </Routes>
  )
}

export default App
