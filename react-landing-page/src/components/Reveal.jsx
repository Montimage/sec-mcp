import React, { useEffect, useRef, useState } from 'react';

/**
 * Scroll-triggered reveal. Uses IntersectionObserver rather than a motion
 * library — this sub-project has its own lockfile and a landing page does not
 * justify the dependency.
 *
 * Reveals once and then unobserves. If IntersectionObserver is unavailable or
 * the visitor prefers reduced motion, content renders visible immediately, so
 * nothing is ever hidden behind an animation that never fires.
 */
const Reveal = ({ children, delay = 0, as: Tag = 'div', className = '', ...rest }) => {
    const ref = useRef(null);
    const [visible, setVisible] = useState(false);

    useEffect(() => {
        const node = ref.current;
        const reduced =
            typeof window !== 'undefined' &&
            window.matchMedia('(prefers-reduced-motion: reduce)').matches;

        if (!node || reduced || typeof IntersectionObserver === 'undefined') {
            setVisible(true);
            return;
        }

        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) {
                    setVisible(true);
                    observer.unobserve(entry.target);
                }
            },
            { threshold: 0.12 }
        );

        observer.observe(node);
        return () => observer.disconnect();
    }, []);

    return (
        <Tag
            ref={ref}
            className={`reveal ${visible ? 'is-visible' : ''} ${className}`}
            style={{ transitionDelay: `${delay}ms` }}
            {...rest}
            onFocusCapture={() => setVisible(true)}
        >
            {children}
        </Tag>
    );
};

export default Reveal;
