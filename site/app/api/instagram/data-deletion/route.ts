import { NextRequest, NextResponse } from "next/server";
import { randomBytes } from "crypto";

/**
 * Meta Data Deletion Request Callback
 * Called when a user requests deletion of their data.
 * Must return JSON with { url, confirmation_code }.
 * https://developers.facebook.com/docs/development/create-an-app/app-dashboard/data-deletion-callback
 */
export async function POST(req: NextRequest): Promise<NextResponse> {
  // Generate a unique confirmation code for this request
  const confirmationCode = randomBytes(8).toString("hex");

  // The url field points to a page where users can check deletion status.
  // We direct them to our privacy page which explains data practices.
  const statusUrl = `${req.nextUrl.origin}/privacy`;

  return NextResponse.json(
    {
      url: statusUrl,
      confirmation_code: confirmationCode,
    },
    { status: 200 }
  );
}
