import React, { FC, useState } from "react";
import { useQuery, useMutation } from "react-query";
import { useNavigate } from "react-router-dom";
import { Table, Typography, Input, Button, Form, Tag, Modal } from "antd";
import { toast } from "react-toastify";
import { Organization } from "../../../../api/api";
import LoadingSpinner from "../../../LoadingSpinner";

interface InviteWithEmailForm extends HTMLFormControlsCollection {
  email: string;
}

interface FormElements extends HTMLFormElement {
  readonly elements: InviteWithEmailForm;
}

const TeamTab: FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [action, setAction] = useState<string | null>(null);
  const [visibleInviteLink, setVisibleInviteLink] = useState(false);
  const [inviteLink, setInviteLink] = useState<string | null>(null);
  const {
    data: organization, // organization is the data returned from the query
    isLoading,
    isError,
    refetch,
  } = useQuery(["organization"], () =>
    Organization.get().then((res) => res[0])
  );

  const handleEmailChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(event.target.value);
  };

  const closeInviteLinkModal = () => {
    setVisibleInviteLink(false);
    setInviteLink(null);
  };

  const inviteMutation = useMutation(
    (data: { email: string }) => Organization.invite(email),
    {
      onSuccess: (response) => {
        toast.success("Invite sent");
        refetch();
      },
      onError: (error: any) => {
        if (error.response.data) {
          toast.error(
            Array.isArray(error.response.data.email)
              ? error.response.data.email[0]
              : error.response.data.email
          );
        } else {
          toast.error("Cannot send an invite now, try again later.");
        }
      },
    }
  );

  const inviteLinkMutation = useMutation(
    (data: { email: string }) => Organization.invite_link(email),
    {
      onSuccess: (response: any) => {
        const link = response.link;
        setInviteLink(link);
        console.log(link);
        if (link) {
          setVisibleInviteLink(true);
        }
        refetch();
      },
      onError: (error: any) => {
        console.log(error.response);
        if (error.response.data.detail) {
          toast.error(error.response.data.detail);
        } else {
          toast.error("Cannot generate an invite link now, try again later.");
        }
      },
    }
  );

  const handleInvite = () => {
    if (action === "sendInvite") {
      inviteMutation.mutate({ email });
    } else if (action === "generateInviteLink") {
      inviteLinkMutation.mutate({ email });
    }
  };

  return (
    <div>
      <Typography.Title level={2}>Team Members</Typography.Title>
      <div className="flex flex-row space-x-10">
        <div className="px-4 sm:px-6 lg:px-8 basis-7/12 border-2 border-solid rounded border-[#EAEAEB]">
          <div className="mt-8 flex flex-col">
            <div className="-my-2 -mx-4 overflow-x-auto sm:-mx-6 lg:-mx-8">
              <div className="inline-block min-w-full align-middle">
                <Table
                  className="min-w-full divide-y divide-gray-200"
                  pagination={false}
                  columns={
                    [
                      {
                        title: "Username",
                        dataIndex: "username",
                        key: "username",
                      },
                      {
                        title: "Email",
                        dataIndex: "email",
                        key: "email",
                      },
                      {
                        title: "Role",
                        dataIndex: "role",
                        key: "role",
                      },
                      {
                        title: "Status",
                        dataIndex: "status",
                        key: "status",
                        render: (status: string) => {
                          const color =
                            status === "Active" ? "green" : "yellow";
                          return (
                            <Tag color={color} key={status}>
                              {status.toUpperCase()}
                            </Tag>
                          );
                        },
                      },
                      {
                        render(text, record) {
                          return (
                            <div className="flex flex-row space-x-2">
                              {/* <Button
                                type="primary"
                                onClick={() => {
                                  console.log(record);
                                }}
                              >
                                Edit
                              </Button> */}
                            </div>
                          );
                        },
                      },
                    ] as any
                  }
                  dataSource={organization?.users}
                />
              </div>
            </div>
          </div>
        </div>
        <div className="basis-5/12 justify-self-center">
          <h2>Invite to Team</h2>
          <div className="w-112">
            <Form onFinish={handleInvite} name="normal_login">
              <Form.Item>
                <label htmlFor="email">Email</label>
                <Input
                  type="text"
                  name="email"
                  value={email}
                  defaultValue="user123@email.com"
                  onChange={handleEmailChange}
                />
              </Form.Item>
            </Form>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <Button
                style={{ marginRight: "6px" }}
                onClick={() => {
                  setAction("sendInvite");
                  handleInvite();
                }}
              >
                Send Invite
              </Button>
              <Button
                style={{ marginLeft: "6px" }}
                onClick={() => {
                  setAction("generateInviteLink");
                  handleInvite();
                }}
              >
                Generate Invite Link
              </Button>
            </div>
          </div>
        </div>
      </div>
      <Modal
        visible={visibleInviteLink}
        title={email + " Invite Link"}
        onCancel={closeInviteLinkModal}
        footer={
          <Button key="Okay" onClick={closeInviteLinkModal} type="primary">
            Okay
          </Button>
        }
      >
        <div className="flex flex-col">
          <p className="text-2xl font-main" />
          <p className="text-lg font-main">
            Your invite link is:{" "}
            {inviteLink ? <Input value={inviteLink} readOnly /> : "Loading..."}
          </p>
        </div>
      </Modal>
      {(action === "sendInvite" && inviteMutation.isLoading) ||
        (action === "generateInviteLink" && inviteLinkMutation.isLoading && (
          <LoadingSpinner />
        ))}
    </div>
  );
};

export default TeamTab;
