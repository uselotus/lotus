// @ts-ignore
import React from 'react'
import './button.css'

interface LotusButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    text: string;
    children?: React.ReactNode;
}

export const LotusButton : React.FunctionComponent<LotusButtonProps> = ({ className, onClick, children, ...rest}) => {
  return (
      <button
          {...rest}
          type="button"
          onClick={onClick}
          className={`lotus-button py-2.5 px-5 mr-2 mb-2 bg-black text-white rounded-lg ${className}`}
          >
          {!!children ? children: rest.text }
      </button>
      )
}
