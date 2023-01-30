import React, { PropsWithChildren } from "react";

interface CardProps {
  className?: string;
  onClick?: VoidFunction;
}
const CustomerCard = ({
  className,
  children,
  onClick,
}: PropsWithChildren<CardProps>) => (
  <div
    className={`min-h-[200px]  min-w-[246px] p-6 cursor-pointer  rounded-sm bg-card  shadow-lg ${
      className && className
    }`}
    onClick={onClick}
    aria-hidden
  >
    {children}
  </div>
);

const CardHeading = ({ children }: PropsWithChildren) => <>{children}</>;

const CardContainer = ({
  className,
  children,
}: PropsWithChildren<CardProps>) => (
  <div className={`mt-2 ${className && className}`}>{children}</div>
);

const CardBlock = ({ className, children }: PropsWithChildren<CardProps>) => (
  <div className={`mt-2 ${className && className}`}>{children}</div>
);

const CardItem = ({ className, children }: PropsWithChildren<CardProps>) => (
  <div
    className={`flex items-center text-card-text justify-between gap-2 mt-6 ${
      className && className
    }`}
  >
    {children}
  </div>
);

CustomerCard.Heading = CardHeading;
CustomerCard.Container = CardContainer;
CustomerCard.Block = CardBlock;
CustomerCard.Item = CardItem;

export default CustomerCard;
