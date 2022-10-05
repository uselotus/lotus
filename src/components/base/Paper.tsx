import { Card } from 'antd'
import React from 'react'

// <Paper color='gold'></Paper>

type Props = {
  color: 'gold' | 'default'
}
export const Paper = (props: Props | any) => {
  return (
    <div
      {...props}
      className={[
        'p-4 rounded-lg',
        props.color === 'gold' ? 'bg-[#CCA43B69]' : 'bg-[#F7F8FD]',
      ].join(' ')}
    />
  )
}
