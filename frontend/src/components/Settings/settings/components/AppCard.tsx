/* eslint-disable import/prefer-default-export */
import { Avatar, Card, Tag } from "antd";
import React from "react";
import { Link } from "react-router-dom";
import { toast } from "react-toastify";

type Props = {
  title: string;
  description: string;
  connected: boolean;
  icon: React.ReactNode;
  handleClick: () => void;
  isNew?: boolean;
  selfHosted?: boolean;
};
export function AppCard({
  title,
  handleClick,
  description,
  connected,
  icon,
  isNew,
  selfHosted,
}: Props) {
  return (
    <div>
      <Card
        style={{
          boxShadow: "0 2px 4px 0 #a8a8a833",
          minHeight: "180px",
        }}
        hoverable
        title={<Avatar shape="square" src={icon} />}
        size="small"
        extra={
          // eslint-disable-next-line no-nested-ternary
          connected ? (
            <Tag color="success">Connected</Tag>
          ) : !selfHosted ? (
            <Tag
              color="default"
              onClick={
                title === "Stripe"
                  ? handleClick
                  : () => {
                      toast.error("Upgrade to get access to this integration");
                    }
              }
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
        {connected ? (
          <div className="flex justify-end pt-4">
            <Link to={title.toLowerCase()}>
              <h3 className="text-darkgold hover:text-black">
                View Integration
              </h3>
            </Link>
          </div>
        ) : (
          <div className="flex justify-end ">
            <h3 className="">-</h3>
          </div>
        )}
      </Card>
    </div>
  );
}
