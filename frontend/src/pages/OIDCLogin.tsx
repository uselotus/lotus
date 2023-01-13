import React, { useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { useMutation } from "react-query";
import { toast } from "react-toastify";

const OIDCLogin: React.FC = () => {
  // TODO: these values need to be parameterised in the application.
  const clientID = "testclient@lotus";
  const redirectURI = window.location.origin + "/authorize";
  const authorizeURL = "https://hello.uselotus.io/oauth/v2/authorize";

  async function doAuthRequest() {
    // We need to generate a Zitadel URL which asks it to log the user in.
    // The actual login process is described in the POC README.
    const requestURL = new URL(authorizeURL);
    const params = requestURL.searchParams;

    // Generate a random challenge string. This is reused when getting the access token.
    // It's part of the PKCE flow. I've written more about this in the POC README and also
    // in the authorise.html page.
    //
    // Generate a random byte array, and then convert it into a challenge string.
    // Note that it's the random string that we need here, not the byte array.
    const randomBytes = new Uint8Array(32);
    crypto.getRandomValues(randomBytes);
    let challengeString = btoa(String.fromCharCode.apply(null, randomBytes));

    // Convert the challenge string into a byte array
    // Note that this is different to the original byte array that we used to generate
    // the string! It's all a bit annoying. :)
    const textEncoder = new TextEncoder();
    const challengeBytes = textEncoder.encode(challengeString);

    // Hash the challenge string, and convert to base64
    const challengeDigest = await crypto.subtle.digest(
      "SHA-256",
      challengeBytes
    );
    let digest64 = btoa(
      String.fromCharCode.apply(null, new Uint8Array(challengeDigest))
    )
      .replace(/\//g, "_")
      .replace(/[+]/g, "-");

    // Store the challenge in session storage for the authorizing page.
    // decode b64 to uint8 with https://stackoverflow.com/a/36046727/6716597
    sessionStorage.setItem("lotusCodeVerifier", challengeString);

    // It appears that padding is stripped off from the encoding.
    digest64 = digest64.replace(/=/g, "");

    // Now, generate a URL that we redirect to. Zitadel then takes over to log
    // the user in. That process might be quite complex, for example it might involve
    // third parties like GitHub or Google.
    params.append("client_id", clientID);
    params.append("redirect_uri", redirectURI); // must be configured in the project
    params.append("response_type", "code");
    params.append("scope", "openid email profile");
    params.append("code_challenge", digest64);
    params.append("code_challenge_method", "S256"); // zitadel requires this to be S256 (= sha256)

    alert(requestURL);

    window.location.href = requestURL.href;
  }

  useEffect(() => {
    doAuthRequest();
  }, []);

  return <div></div>;
};

export default OIDCLogin;
