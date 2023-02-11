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
  handleClickId: () => void;
  isNew?: boolean;
  selfHosted?: boolean;
  idName?: string;
  idValue?: string;
};

export function AppCard({
  title,
  handleClickConnect,
  handleClickId,
  description,
  connected,
  icon,
  isNew,
  selfHosted,
  idName,
  idValue,
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
          <>
            {idName ? (
              <Tag onClick={handleClickId} style={{ cursor: "pointer" }}>
                <b>{idName}:</b> {idValue || "-"}
              </Tag>
            ) : null}
            {(idValue || selfHosted) && connected ? (
              <Tag color="success">Connected</Tag>
            ) : !selfHosted && !idValue ? null : !selfHosted ? (
              <Tag
                color="default"
                onClick={
                  idValue
                    ? title.includes("Stripe") || title.includes("Braintree")
                      ? handleClickConnect
                      : () => {
                          console.log("title", title);
                          toast.error(
                            "Upgrade to get access to this integration"
                          );
                        }
                    : () => {
                        toast.error("Account Not Linked");
                      }
                }
                style={{ cursor: "pointer" }}
              >
                {idValue ? "Connect" : "Account Not Linked"}
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
