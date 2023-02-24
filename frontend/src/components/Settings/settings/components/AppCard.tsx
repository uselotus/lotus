import { Avatar, Card, Tag } from "antd";
import React from "react";
import { Link } from "react-router-dom";
import { toast } from "react-toastify";

type Props = {
  title: string;
  description: string;
  connected: boolean;
  icon: React.ReactNode;
  handleClickConnect: () => void;
  isNew?: boolean;
  selfHosted?: boolean;
  idName?: string;
  idValue?: string;
  working?: boolean;
};

export function AppCard({
  title,
  handleClickConnect,
  description,
  connected,
  icon,
  isNew,
  selfHosted,
  idName,
  idValue,
  working,
}: Props) {
  const link = title.toLowerCase().includes("stripe")
    ? "stripe"
    : title.toLowerCase().includes("braintree")
    ? "braintree"
    : title.toLowerCase();
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
          <>
            {working && (idValue || selfHosted) && connected ? (
              <Tag color="success">Connected</Tag>
            ) : !selfHosted ? (
              <Tag
                color="default"
                onClick={
                  title.includes("Stripe") || title.includes("Braintree")
                    ? handleClickConnect
                    : () => {
                        toast.error(
                          "Upgrade to get access to this integration"
                        );
                      }
                }
                style={{ cursor: "pointer" }}
              >
                Connect
              </Tag>
            ) : (
              <Tag color="default">No API Key</Tag>
            )}
          </>
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
        {idName ? (
          <div className="flex justify-end pt-4">
            <Tag style={{ cursor: "pointer" }}>
              <b>{idName}:</b> {idValue || "-"}
            </Tag>
          </div>
        ) : null}
        {connected ? (
          <div className="flex justify-end pt-4">
            <Link to={link}>
              <h3 className="text-darkgold hover:text-black">
                View Integration
              </h3>
            </Link>
          </div>
        ) : null}
      </Card>
    </div>
  );
}
