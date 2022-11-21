// @ts-ignore
import React from 'react'
import './button.css'

interface LotusButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
    text: string;
    children?: React.ReactNode;
}

export const LotusFilledButton : React.FunctionComponent<LotusButtonProps> = ({ className, onClick, children, ...rest}) => {
  return (
      <button
          {...rest}
          type="button"
          onClick={onClick}
          className={`lotus-button lotus-filled-button ${className}`}
          >
          {!!children ? children: rest.text }
      </button>
      )
}

export const LotusOutlinedButton : React.FunctionComponent<LotusButtonProps> = ({ className, onClick, children, ...rest}) => {
  return (
      <button
          {...rest}
          type="button"
          onClick={onClick}
          className={`lotus-button lotus-outlined-button ${className}`}
          >
          {!!children ? children: rest.text }
      </button>
      )
}
