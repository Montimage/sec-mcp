import React from 'react';

/**
 * The sec-mcp mark: a shield drawn as hairline geometry rather than a filled
 * gradient blob. The scan grid reads as "inspection", the check as "verdict".
 * Frame inherits currentColor; only the check carries the signal green, which
 * keeps the mark legible if it is ever placed on a light surface.
 */
const Logo = ({ className = 'h-7 w-7' }) => (
    <svg
        className={className}
        viewBox="0 0 32 32"
        fill="none"
        aria-hidden="true"
        focusable="false"
    >
        <path
            d="M16 2.5 28 7v10.2c0 6.6-5.1 10.9-12 12.3-6.9-1.4-12-5.7-12-12.3V7l12-4.5Z"
            stroke="currentColor"
            strokeWidth="1.25"
            strokeLinejoin="round"
            opacity="0.62"
        />
        <path
            d="M4 12.4h24M4 18.2h24M16 2.5v27"
            stroke="currentColor"
            strokeWidth="0.75"
            opacity="0.22"
        />
        <path
            d="M10.4 16.2 14.4 20.3 21.9 12.4"
            stroke="#22C55E"
            strokeWidth="2"
            strokeLinecap="square"
            fill="none"
        />
    </svg>
);

export default Logo;
