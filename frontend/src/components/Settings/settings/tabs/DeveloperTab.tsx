import {
  Button,
  Divider,
  Typography,
  Modal,
  Input,
  message,
  Popconfirm,
  Table,
  Menu,
  Dropdown,
  Checkbox,
} from "antd";
import React, { useState } from "react";
import { useQuery, useMutation, QueryClient } from "react-query";
import { Webhook, APIToken } from "../../../../api/api";
import { DeleteOutlined, MoreOutlined } from "@ant-design/icons";
import { Paper } from "../../../base/Paper";
import { toast } from "react-toastify";
import {
  WebhookEndpoint,
  WebhookEndpointCreate,
  WebhookEndpointUpdate,
} from "../../../../types/webhook-type";

function isValidHttpUrl(string) {
  let url;
  try {
    url = new URL(string);
  } catch (_) {
    return false;
  }
  return url.protocol === "https:";
}
export const DeveloperTab = () => {
  const [visible, setVisible] = useState<boolean>(false);
  const [visibleWebhook, setVisibleWebhook] = useState<boolean>(false);
  const [apiKey, setApiKey] = useState<string>("");
  const queryClient = new QueryClient();
  const [webhookName, setWebhookName] = useState<string>("");
  const [webhookUrl, setWebhookUrl] = useState<string>("");
  const [webhookSelected, setWebhookSelected] = useState<WebhookEndpoint>();
  const [isInvoiceGenerated, setIsInvoiceGenerated] = useState<boolean>(false);
  const closeModal = () => {
    setVisible(false);
    setApiKey("");
  };

  const closeWebhookModal = () => {
    setVisibleWebhook(false);
  };
  const webhookMenu = (
    <Menu>
      {/* <Menu.Item
        key="1"
        onClick={() => {
          setWebhookUrl(webhookSelected?.webhook_url || "");
          setWebhookName(webhookSelected?.name || "");

          if (
            webhookSelected?.triggers &&
            webhookSelected?.triggers.length > 0 &&
            webhookSelected?.triggers[0]["trigger_name"] === "invoice.created"
          ) {
            setIsInvoiceGenerated(true);
          } else {
            setIsInvoiceGenerated(false);
          }

          setWebhookName(webhookSelected?.name || "");

          setVisibleWebhook(true);
        }}
      >
        <div className="planMenuArchiveIcon">
          <div className=" text-black">Edit</div>
        </div>
      </Menu.Item> */}
      <Menu.Item
        key="2"
        onClick={() => handleDeleteUrl(webhookSelected?.webhook_endpoint_id)}
      >
        <div className="planMenuArchiveIcon">
          <div className="archiveLabel">Delete</div>
        </div>
      </Menu.Item>
    </Menu>
  );

  const {
    status: alertStatus,
    error: webhookError,
    data: webhookData,
    isLoading,
  } = useQuery<any>("urls", Webhook.getEndpoints);

  const getKey = () => {
    APIToken.newAPIToken().then((data) => {
      setApiKey(data.api_key);
    });
    setVisible(true);
  };

  const handleAddUrl = () => {
    if (isValidHttpUrl(webhookUrl)) {
      let triggers: string[];
      if (isInvoiceGenerated) {
        triggers = ["invoice.created"];
      } else {
        triggers = [];
      }

      let endpointPost: WebhookEndpointCreate = {
        name: webhookName,
        webhook_url: new URL(webhookUrl),
        triggers_in: triggers,
      };
      Webhook.createEndpoint(endpointPost)
        .then((data: WebhookEndpoint) => {
          setWebhookUrl("");
          setWebhookName("");
          setIsInvoiceGenerated(false);
          toast.success("Webhook URL added successfully");
          queryClient.invalidateQueries("urls");
          setVisibleWebhook(false);
          setWebhookSelected(undefined);
        })
        .catch((error) => {
          toast.error(error.response.data.non_field_errors[0]);
        });
    } else {
      toast.error("Please enter a valid URL starting with https://");
    }
  };

  const handleDeleteUrl = (id: string | undefined) => {
    if (id) {
      Webhook.deleteEndpoint(id)
        .then((data) => {
          message.success("Webhook URL deleted successfully");
          queryClient.invalidateQueries("urls");
          setWebhookSelected(undefined);
        })
        .catch((err) => {
          message.error("Error deleting webhook URL");
        });
    }
  };

  if (isLoading) return <div>Loading...</div>;
  return (
    <div>
      <div>
        <Typography.Title level={2}>API Keys</Typography.Title>
        <Typography.Paragraph>
          Requesting a new API key will revoke your existing key! Store your key
          safely.
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
      <div className="mt-10 flex flex-row justify-between w-full mb-8">
        <Typography.Title level={2}>Webhooks</Typography.Title>
        <Button
          type="primary"
          onClick={() => {
            setWebhookUrl("");
            setWebhookName("");
            setVisibleWebhook(true);
          }}
        >
          Add URL
        </Button>
      </div>

      <div className="border-2 border-solid rounded border-[#EAEAEB]">
        <Table
          dataSource={webhookData}
          pagination={false}
          columns={[
            {
              title: "Name",
              dataIndex: "name",
              key: "name",
            },
            {
              title: "Webhook URL",
              dataIndex: "webhook_url",
              key: "webhook_url",
            },
            {
              title: "Webhook Secret",
              dataIndex: "webhook_secret",
              key: "webhook_secret",
            },
            {
              title: "Triggers",
              dataIndex: "triggers",
              key: "triggers",
              render: (triggers: object[]) => {
                return (
                  <div>
                    {triggers.map((trigger) => {
                      return (
                        <div>
                          {"["} {trigger["trigger_name"]} {"]"}
                        </div>
                      );
                    })}
                  </div>
                );
              },
            },
            {
              key: "action",
              width: 100,
              render: (text: any, record: any) => (
                <Dropdown overlay={webhookMenu} trigger={["click"]}>
                  <Button
                    type="text"
                    size="small"
                    onClick={(e) => {
                      setWebhookSelected(record);
                      e.preventDefault();
                    }}
                  >
                    <MoreOutlined />
                  </Button>
                </Dropdown>
              ),
            },
          ]}
        />
      </div>

      <Modal
        visible={visibleWebhook}
        title="Webhook URL"
        onCancel={closeWebhookModal}
        footer={
          <Button key="Confirm URL" onClick={handleAddUrl} type="primary">
            Confirm
          </Button>
        }
      >
        <div className="flex flex-col space-y-8">
          <p className="text-lg font-main">Endpoint Name:</p>
          <Input
            value={webhookName}
            onChange={(e) => setWebhookName(e.target.value)}
          ></Input>
          <p className="text-lg font-main">Endpoint URL:</p>
          <Input
            value={webhookUrl}
            onChange={(e) => setWebhookUrl(e.target.value)}
          ></Input>
          <p className="text-lg font-main">Events Subscribed To:</p>
          <div className="grid grid-cols-auto">
            <Checkbox
              onChange={(e) => setIsInvoiceGenerated(e.target.checked)}
              value={isInvoiceGenerated}
            >
              <p className="text-lg font-main">invoice.created</p>
            </Checkbox>
          </div>
        </div>
      </Modal>

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
