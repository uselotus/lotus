import {
  Button,
  Divider,
  Typography,
  Modal,
  Input,
  message,
  Popconfirm,
} from "antd";
import React, { useState } from "react";
import { useQuery } from "react-query";
import { Alerts, APIToken } from "../../../../api/api";
import { DeleteOutlined } from "@ant-design/icons";

export const DeveloperTab = () => {
  const [visible, setVisible] = useState<boolean>(false);
  const [apiKey, setApiKey] = useState<string>("");
  const [webhookUrl, setWebhookUrl] = useState<string>("");
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
  console.log(webhookData);

  const getKey = () => {
    APIToken.newAPIToken().then((data) => {
      setApiKey(data.api_key);
    });
    setVisible(true);
  };

  const handleAddUrl = () => {
    if (webhookUrl.includes("https://")) {
      Alerts.addUrl(webhookUrl)
        .then((data) => {
          setWebhookUrl("");
          message.success("Webhook URL added successfully");
        })
        .catch((err) => {
          message.error("Webhook URL already exists");
        });
    } else {
      message.error("Please enter a valid URL");
    }
  };

  const handleDeleteUrl = (id: number) => {
    Alerts.deleteUrl(id)
      .then((data) => {
        message.success("Webhook URL deleted successfully");
      })
      .catch((err) => {
        message.error("Error deleting webhook URL");
      });
  };

  if (isLoading) return <div>Loading...</div>;
  return (
    <div>
      <div>
        <Typography.Title level={2}>API Keys</Typography.Title>
        <Typography.Paragraph>
          Getting a new API key will revoke your existing key!
        </Typography.Paragraph>
        <Popconfirm
          title="Are you sure to want to revoke your existing key?"
          onConfirm={getKey}
          okText="Yes"
        >
          <Button type="primary">Revoke API Key</Button>
        </Popconfirm>
      </div>
      <Divider />
      {/* <div className="mt-10 flex flex-row">
        <Typography.Title level={2}>Webhook URLs</Typography.Title>
      </div>
      <div>
        <table className="table-auto">
          <tr className="flex">
            <td className="pr-4">Webhooks URL:</td>
            <td className="w-[400px]">
              <div>
                <Input.Group compact className="mb-2">
                  <Input
                    style={{ width: "calc(100% - 90px)" }}
                    onChange={(e) => setWebhookUrl(e.target.value)}
                    placeholder="New Url"
                    value={webhookUrl}
                  />
                  <Button type="primary" onClick={handleAddUrl}>
                    Add URL
                  </Button>
                </Input.Group>
                {webhookData.map((webhook, index) => (
                  <div className="mb-2" key={index}>
                    <Paper>
                      <div className="flex flex-row justify-between align-middle">
                        <Typography.Text>{webhook.webhook_url}</Typography.Text>
                        <Button
                          size="small"
                          type="text"
                          icon={<DeleteOutlined />}
                          danger
                          onClick={() => {
                            handleDeleteUrl(webhook.id);
                          }}
                        />
                      </div>
                    </Paper>
                  </div>
                ))}
              </div>
            </td>
          </tr>
        </table>
      </div> */}
      <Modal
        visible={visible}
        title="New API Key"
        onCancel={closeModal}
        footer={
          <Button key="Okay" onClick={closeModal} type="primary">
            Okay
          </Button>
        }
      >
        <div className="flex flex-col">
          <p className="text-2xl font-main"></p>
          <p className="text-lg font-main">
            Your previous key has been revoked
          </p>
          <p className="text-lg font-main">
            Your new key is:{" "}
            {apiKey ? <Input value={apiKey} readOnly /> : "Loading..."}
          </p>
          <p></p>
        </div>
      </Modal>
    </div>
  );
};
