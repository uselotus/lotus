import { Button, Divider, Typography, Modal, Descriptions, Input } from "antd";
import React, { useState } from "react";
import { useQuery } from "react-query";
import { Alerts, APIToken } from "../../../api/api";
import { Paper } from "../../../components/base/Paper";
import { StripeStatusType } from "../../../types/stripe-type";
import { DeleteOutlined } from "@ant-design/icons";

export const DeveloperTab = () => {
  const [visible, setVisible] = useState<boolean>(false);
  const [apiKey, setApiKey] = useState<string>("");

  const closeModal = () => {
    setVisible(false);
    setApiKey("");
  };

  const {
    status: alertStatus,
    error: webhookError,
    data: webhookData,
    isLoading,
  } = useQuery<any>(["urls"], Alerts.getUrls);

  const getKey = () => {
    APIToken.newAPIToken().then((data) => {
      setApiKey(data.api_key);
    });
    setVisible(true);
  };
  console.log(webhookData);
  if (isLoading) return <div>Loading...</div>;
  return (
    <div>
      <div className="mt-10 flex flex-row">
        <Button onClick={getKey}>Revoke API Key</Button>
      </div>
      <Divider />
      <div className="mt-10 flex flex-row">
        <Typography.Title level={2}>Webhook URLs</Typography.Title>
      </div>
      <div className="w-[500px]">
        <Descriptions>
          <Descriptions.Item label="Webhook URL">
            <Input.Group compact className="mb-2">
              <Input
                style={{ width: "calc(100% - 90px)" }}
                placeholder="New Url"
              />
              <Button type="primary">Add URL</Button>
            </Input.Group>
            {[
              "https://webhook.site/4f1b1b1b1b1b",
              "https://webhook.site/4f1b1b1b1b1b",
              "https://webhook.site/4f1b1b1b1b1b",
              "https://webhook.site/4f1b1b1b1b1b",
            ].map((url, index) => (
              <Paper className="mb-2 block" key={index}>
                <div className="flex flex-row justify-between align-middle">
                  <Typography.Text>{url}</Typography.Text>
                  <Button
                    size="small"
                    type="text"
                    icon={<DeleteOutlined />}
                    danger
                    onClick={() => {}}
                  />
                </div>
              </Paper>
            ))}
          </Descriptions.Item>
        </Descriptions>
      </div>
      <Modal
        visible={visible}
        footer={
          <Button key="ok" onClick={closeModal}>
            Ok
          </Button>
        }
      >
        <div className="flex flex-col">
          <p className="text-2xl font-main">New API Key</p>
          <p className="text-lg font-main">
            Your previous key has been revoked
          </p>
          <p className="text-lg font-main">
            Your new key is: {apiKey ? apiKey : "Loading..."}
          </p>
          <p></p>
        </div>
      </Modal>
    </div>
  );
};
