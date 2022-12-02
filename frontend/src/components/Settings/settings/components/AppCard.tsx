import { Avatar, Card, Tag } from "antd";
import React from "react";
import { Link } from "react-router-dom";

type Props = {
  title: string;
  description: string;
  connected: boolean;
  icon: React.ReactNode;
  handleClick: () => void;
  isNew?: boolean;
  selfHosted?: boolean;
};
export const AppCard = ({
  title,
  handleClick,
  description,
  connected,
  icon,
  isNew,
  selfHosted,
}: Props) => {
  return (
    <div>
      <Card
        style={{
          boxShadow: "0 2px 4px 0 #a8a8a833",
        }}
        hoverable={true}
        title={<Avatar shape="square" src={icon} />}
        size="small"
        extra={
          connected ? (
            <Tag color="success">Connected</Tag>
          ) : !selfHosted ? (
            <Tag
              color="default"
              onClick={handleClick}
              style={{ cursor: "pointer" }}
            >
              Connect
            </Tag>
          ) : (
            <Tag
              color="default"
              onClick={handleClick}
              style={{ cursor: "pointer" }}
            >
              No API Key
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
        <div className="separator pt-4" />
        {connected && (
          <div className="flex justify-end pt-4">
            <Link to={title.toLowerCase()}>
              <h3 className="text-darkgold">View Integration</h3>
            </Link>
          </div>
        )}
      </Card>
    </div>
  );
};
