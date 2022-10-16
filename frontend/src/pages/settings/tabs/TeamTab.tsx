import React, { FC, useState } from "react";
import { useQuery, useMutation } from "react-query";
import { useNavigate } from "react-router-dom";
import { Divider, Typography, Row, Col, Input, Button, Form } from "antd";
import { Organization } from "../../../api/api";
import { toast } from "react-toastify";
import LoadingSpinner from "../../../components/LoadingSpinner";

interface InviteWithEmailForm extends HTMLFormControlsCollection {
  email: string;
}

interface FormElements extends HTMLFormElement {
  readonly elements: InviteWithEmailForm;
}

const TeamTab: FC = () => {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");

  const {
    data: organization,
    isLoading,
    isError,
  } = useQuery(["organization"], () =>
    Organization.get().then((res) => {
      return res;
    })
  );

  const handleEmailChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setEmail(event.target.value);
  };

  const mutation = useMutation(
    (data: { email: string }) => Organization.invite(email),
    {
      onSuccess: (response) => {
        toast.success("Invite sent");
      },
      onError: (error) => {
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

  console.log("organization", organization);

  const handleSendInviteEmail = (event: React.FormEvent<FormElements>) => {
    mutation.mutate({ email });
  };

  return (
    <div>
      <Typography.Title level={2}>Team Members</Typography.Title>

      <Row gutter={[0, 24]}>
        { organization?.team_members?.map((member, key) => (
          <Col span={24} key={key}>
            {member}
          </Col>
        ))}
      </Row>

      <Divider />
      <Typography.Title level={4}>Invite to Team</Typography.Title>
      <div className="w-96">
        <Form onFinish={handleSendInviteEmail} name="normal_login">
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
          <Form.Item>
            <Button htmlType="submit">Send Invite</Button>
          </Form.Item>
        </Form>
      </div>
      {mutation.isLoading && <LoadingSpinner />}
    </div>
  );
};

export default TeamTab;
