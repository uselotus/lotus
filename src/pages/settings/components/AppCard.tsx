import { Avatar, Card, Tag } from "antd";
import React from "react";

type Props = {
  title: string;
  description: string;
  connected: boolean;
  icon: React.ReactNode;
  handleClick: () => void;
  isNew?: boolean;
};
export const AppCard = ({
  title,
  handleClick,
  description,
  connected,
  icon,
  isNew,
}: Props) => {
  return (
    <div>
      <Card
        style={{
          boxShadow: "0 2px 4px 0 #a8a8a833",
        }}
        title={<Avatar shape="square" src={icon} />}
        size="small"
        extra={
          connected ? (
            <Tag color="success">Connected</Tag>
          ) : (
            <Tag
              color="default"
              onClick={handleClick}
              style={{ cursor: "pointer" }}
            >
              Connect
            </Tag>
          )
        }
      >
        <Card.Meta
          title={
            <>
              {title} {isNew && <Tag color="blue">New</Tag>}
            </>
          }
          description={description}
        />
      </Card>
    </div>
  );
};
