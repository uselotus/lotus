/* eslint-disable react/jsx-no-useless-fragment */
/* eslint-disable react/no-unused-prop-types */
import React, { PropsWithChildren } from "react";

interface CardProps {
  className?: string;
  onClick?: VoidFunction;
}
function CustomerCard({
  className,
  children,
  onClick,
}: PropsWithChildren<CardProps>) {
  return (
    <div
      className={`min-h-[200px]  min-w-[246px] p-6 cursor-pointer  rounded-sm bg-card  ${
        className && className
      }`}
      onClick={onClick}
      aria-hidden
    >
      {children}
    </div>
  );
}

function CardHeading({ children }: PropsWithChildren) {
  return <>{children}</>;
}

function CardContainer({ className, children }: PropsWithChildren<CardProps>) {
  return <div className={`mt-2 ${className && className}`}>{children}</div>;
}

function CardBlock({ className, children }: PropsWithChildren<CardProps>) {
  return <div className={`mt-2 ${className && className}`}>{children}</div>;
}

function CardItem({ className, children }: PropsWithChildren<CardProps>) {
  return (
    <div
      className={`flex items-center text-card-text justify-between gap-2 mt-6 ${
        className && className
      }`}
    >
      {children}
    </div>
  );
}

CustomerCard.Heading = CardHeading;
CustomerCard.Container = CardContainer;
CustomerCard.Block = CardBlock;
CustomerCard.Item = CardItem;

export default CustomerCard;
