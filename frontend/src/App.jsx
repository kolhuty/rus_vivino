
import { BrowserRouter, Routes, Route } from 'react-router-dom';

import Camera from './components/Camera.jsx'
import Sommelier from './components/Sommelier.jsx'
import './styles/App.css'


function App() {
  return (
    <BrowserRouter>
      <Routes>  // lets say camera app opens at root "/" 
        <Route path="/" element={<Camera />} />
        <Route path="/sommelier" element={<Sommelier />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
