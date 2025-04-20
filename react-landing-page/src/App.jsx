import React from 'react';
import Header from './components/Header';
import Hero from './components/Hero';
import Features from './components/Features';
import Installation from './components/Installation';
import APIReference from './components/APIReference';
import MCPServer from './components/MCPServer';
import Footer from './components/Footer';

const App = () => {
  return (
    <div className="flex flex-col min-h-screen">
      <Header />
      <main className="flex-grow">
        <Hero />
        <Features />
        <MCPServer />
        <Installation />
        <APIReference />
      </main>
      <Footer />
    </div>
  );
};

export default App;