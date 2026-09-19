import React from 'react';
import Header from './components/Header';
import Hero from './components/Hero';
import Features from './components/Features';
import Sources from './components/Sources';
import MCPServer from './components/MCPServer';
import Installation from './components/Installation';
import APIReference from './components/APIReference';
import Footer from './components/Footer';

const App = () => (
    // .grain lays a fixed film-grain tile over everything, so the black
    // canvas has texture instead of reading as a flat fill.
    <div className="grain min-h-screen bg-void">
        <a className="skip-link" href="#main">
            Skip to content
        </a>

        <Header />

        <main id="main" tabIndex={-1}>
            <Hero />
            <Features />
            <Sources />
            <MCPServer />
            <Installation />
            <APIReference />
        </main>

        <Footer />
    </div>
);

export default App;
